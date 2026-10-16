"""Tests for the crawler module — unit tests that don't hit the network."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from ingestion.crawler import CrawlResult, load_robots_txt


def test_crawl_result_creation() -> None:
    """CrawlResult should store url, status, and optional fields."""
    result = CrawlResult(url="https://example.com", status="fetched", html="<html></html>")
    assert result.url == "https://example.com"
    assert result.status == "fetched"
    assert result.html == "<html></html>"
    assert result.error is None


def test_crawl_result_failed() -> None:
    """A failed CrawlResult should store the error message."""
    result = CrawlResult(url="https://example.com", status="failed", error="timeout")
    assert result.status == "failed"
    assert result.error == "timeout"
    assert result.html is None


@pytest.mark.asyncio
async def test_load_robots_txt_handles_failure() -> None:
    """If robots.txt can't be fetched, the parser should allow all URLs."""
    with patch("ingestion.crawler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        rp = await load_robots_txt("https://example.com")
        # Should not crash — and should have allow_all set
        assert rp is not None
        assert rp.can_fetch("*", "https://example.com/any/path") is True


def test_wildcard_robots_parser_real_site_rules() -> None:
    """Verify WildcardRobotParser handles real rules from support.brilliantdirectories.com/robots.txt,
    specifically wildcards (*), end anchors ($), and Allow vs Disallow specificity.
    """
    from ingestion.robots_parser import WildcardRobotParser

    real_rules = [
        "User-agent: *",
        "Disallow: /support/search",
        "Disallow: /support/tickets/",
        "Disallow: /support/login",
        "Disallow: /support/login-verification",
        "Disallow: /login/normal/",
        "Allow: /helpdesk/attachments",
        "Disallow: /helpdesk/",
        "Disallow: /public/tickets/",
        "Disallow: /*/hit$",
        "Sitemap: https://support.brilliantdirectories.com/support/sitemap.xml",
    ]

    parser = WildcardRobotParser()
    parser.parse(real_rules)

    # 1. Normal knowledge base articles should be ALLOWED
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/support/solutions/articles/123-guide") is True

    # 2. Exact Disallow prefixes must be BLOCKED
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/support/search") is False
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/support/search?q=leads") is False
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/support/tickets/456") is False
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/support/login") is False

    # 3. Allow rule takes precedence over Disallow rule if more specific (RFC 9309 longest-match)
    # /helpdesk/attachments (len 21) beats /helpdesk/ (len 10)
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/helpdesk/attachments/screenshot.png") is True
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/helpdesk/general-ticket") is False

    # 4. Wildcard and end anchor /*/hit$ must BLOCK paths ending in /hit
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/support/solutions/articles/12000099791/hit") is False
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/something/hit") is False
    # But path continuing after /hit must NOT match the $ anchor
    assert parser.can_fetch("*", "https://support.brilliantdirectories.com/something/hit/more") is True
