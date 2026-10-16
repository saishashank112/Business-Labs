"""Wildcard and anchor-aware robots.txt parser (RFC 9309 / Google compliant).

Fixes limitations of Python's standard urllib.robotparser:
- Supports '*' wildcard (matching 0 or more characters)
- Supports '$' end-of-path anchor (e.g. '/*/hit$')
- Implements RFC 9309 longest-match precedence between Allow and Disallow rules
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RobotRule:
    path_pattern: str
    is_allow: bool
    regex: re.Pattern
    pattern_len: int


class WildcardRobotParser:
    """A robots.txt parser supporting '*' wildcards and '$' end anchors."""

    def __init__(self, user_agent: str = "*"):
        self.user_agent = user_agent.lower()
        self.rules: list[RobotRule] = []
        self.sitemaps: list[str] = []
        self.allow_all: bool = False

    def _compile_pattern_to_regex(self, pattern: str) -> re.Pattern:
        """Translates robots.txt path pattern with * and $ into a regex."""
        # Check if pattern ends with $ anchor
        has_end_anchor = pattern.endswith("$")
        clean_pat = pattern[:-1] if has_end_anchor else pattern

        # Split pattern by '*' so we can escape literal parts safely
        parts = clean_pat.split("*")
        escaped_parts = [re.escape(p) for p in parts]
        regex_str = ".*".join(escaped_parts)

        # Robots.txt rules always match from start of URL path
        if not regex_str.startswith("^"):
            regex_str = "^" + regex_str

        if has_end_anchor:
            regex_str = regex_str + "$"

        return re.compile(regex_str)

    def parse(self, lines: list[str]) -> None:
        """Parse lines of a robots.txt file."""
        self.rules.clear()
        self.sitemaps.clear()

        current_agents: list[str] = []
        applies_to_target = False

        for raw_line in lines:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue

            if ":" not in line:
                continue

            field, value = line.split(":", 1)
            field = field.strip().lower()
            value = value.strip()

            if field == "user-agent":
                agent = value.lower()
                current_agents.append(agent)
                applies_to_target = (agent == "*" or agent == self.user_agent)

            elif field == "sitemap":
                self.sitemaps.append(value)

            elif field in ("disallow", "allow"):
                if not applies_to_target:
                    continue

                if not value:
                    # Empty Disallow means "allow everything"
                    if field == "disallow":
                        continue

                is_allow = (field == "allow")
                pattern = value
                # Ensure leading slash for path matching
                if not pattern.startswith("/") and not pattern.startswith("*"):
                    pattern = "/" + pattern

                rule_regex = self._compile_pattern_to_regex(pattern)
                self.rules.append(
                    RobotRule(
                        path_pattern=pattern,
                        is_allow=is_allow,
                        regex=rule_regex,
                        pattern_len=len(pattern),
                    )
                )

    def can_fetch(self, user_agent: str, url: str) -> bool:
        """Checks whether user_agent is allowed to fetch url.

        Precedence (RFC 9309 section 2.2.2):
        - Longest matching pattern wins.
        - If match lengths are equal, Allow beats Disallow.
        - If no rule matches, default is Allowed (True).
        """
        if self.allow_all:
            return True

        parsed = urllib.parse.urlparse(url)
        path = parsed.path or "/"
        if parsed.query:
            path_with_query = f"{path}?{parsed.query}"
        else:
            path_with_query = path

        matching_rules: list[RobotRule] = []
        for rule in self.rules:
            # Check against path or path+query
            if rule.regex.search(path) or rule.regex.search(path_with_query):
                matching_rules.append(rule)

        if not matching_rules:
            return True

        # Sort by pattern length descending. If equal length, allow (True) comes before disallow (False)
        matching_rules.sort(key=lambda r: (r.pattern_len, 1 if r.is_allow else 0), reverse=True)
        best_rule = matching_rules[0]
        return best_rule.is_allow
