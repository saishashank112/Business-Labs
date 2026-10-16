"""Tests exposing offline_heuristic risks on informal and messy transcripts.

Demonstrates that offline_heuristic relies strictly on:
1. Hardcoded speaker filtering (checks for 'alex')
2. Exact keyword matches ('twilio', 'sms', 'two-factor', '2fa', 'newsletter')
3. Hardcoded intent substitution (replaces client statement with a fixed string)
4. Assumes follow-up status only by transcript_id containing 'transcript_c' or 'follow'
"""

import json
from pathlib import Path
from agents.transcript_analyst import _extract_offline_heuristic


def test_messy_transcript_1_newsletter_drop():
    """Messy transcript 1: 'let's drop the newsletter thing'
    Because it mentions 'newsletter' and id contains 'follow', it maps to the fixed removal intent.
    However, if evaluated under baseline mode, the exact same words would mistakenly ADD the requirement!
    """
    fpath = Path(__file__).parent.parent / "transcripts" / "transcript_messy_1.json"
    data = json.loads(fpath.read_text(encoding="utf-8"))

    # When evaluated as follow-up
    reqs_followup = _extract_offline_heuristic("transcript_messy_1_followup", "proj_lawyers_directory", data["dialogue"])
    assert len(reqs_followup) == 1
    assert "newsletter" in reqs_followup[0].description.lower()
    assert reqs_followup[0].extraction_mode == "offline_heuristic"

    # CRITICAL RISK: When evaluated without 'follow' in transcript_id (baseline mode)
    # The heuristic looks for keyword 'newsletter' and mistakenly ADDS the feature that the user wanted to drop!
    reqs_baseline = _extract_offline_heuristic("transcript_messy_1_init", "proj_lawyers_directory", data["dialogue"])
    assert len(reqs_baseline) == 1
    assert "Monthly legal newsletter campaign broadcast" in reqs_baseline[0].description
    # Proves the heuristic cannot understand negation or context without LLM!


def test_messy_transcript_2_missing_keywords():
    """Messy transcript 2: 'can we also text people a code when they log in'
    The client clearly requests SMS 2FA, but omits the exact keywords 'twilio', 'sms', 'two-factor', '2fa'.
    Result: offline_heuristic extracts 0 requirements!
    """
    fpath = Path(__file__).parent.parent / "transcripts" / "transcript_messy_2.json"
    data = json.loads(fpath.read_text(encoding="utf-8"))

    reqs = _extract_offline_heuristic("transcript_messy_2_followup", "proj_lawyers_directory", data["dialogue"])
    # Extractor completely misses the requirement because of keyword absence
    assert len(reqs) == 0, "offline_heuristic fails silently on natural wording like 'text people a code'"


def test_messy_transcript_3_relative_timeline_omission():
    """Messy transcript 3: 'we need this a couple of weeks later'
    The client asks for a timeline change, but doesn't supply ISO dates or target keywords.
    Result: offline_heuristic extracts 0 items and does not capture any schedule shift.
    """
    fpath = Path(__file__).parent.parent / "transcripts" / "transcript_messy_3.json"
    data = json.loads(fpath.read_text(encoding="utf-8"))

    reqs = _extract_offline_heuristic("transcript_messy_3_followup", "proj_lawyers_directory", data["dialogue"])
    # Extractor extracts nothing
    assert len(reqs) == 0
