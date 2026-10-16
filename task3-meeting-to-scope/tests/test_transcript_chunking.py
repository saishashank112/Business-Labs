"""Tests for user transcript ingestion and staged chunking.

Verifies:
- Dropping user transcripts into transcripts_user/ as .txt files
- Line parsing for 'Speaker: text' with optional timestamps
- Verification of test_messy_150lines.txt containing >= 150 lines
- Staged chunking into multiple overlapping windows
- Merge step consolidation of duplicate intents
"""

from pathlib import Path
import pytest
from agents.transcript_analyst import (
    parse_transcript_text,
    staged_chunk_dialogue,
    merge_extracted_requirements,
    extract_requirements_from_dialogue,
)
from app.models import Requirement
from app.config import settings


def test_messy_user_transcript_line_count_and_parsing():
    """Verify test_messy_150lines.txt has >= 150 lines and parses cleanly."""
    transcript_file = Path(__file__).parent.parent / "transcripts_user" / "test_messy_150lines.txt"
    assert transcript_file.exists(), f"Missing test fixture: {transcript_file}"

    raw_text = transcript_file.read_text(encoding="utf-8")
    lines = [line for line in raw_text.splitlines() if line.strip()]
    assert len(lines) >= 150, f"Expected at least 150 lines, got {len(lines)}"

    dialogue = parse_transcript_text(raw_text)
    assert len(dialogue) >= 50, f"Expected parsed dialogue turns >= 50, got {len(dialogue)}"

    # Check structure of parsed turns
    assert "speaker" in dialogue[0]
    assert "text" in dialogue[0]
    assert "timestamp" in dialogue[0]
    assert dialogue[0]["speaker"] == "Alex Rivera"


def test_staged_chunking_and_merge_step():
    """Verify dialogue chunking into stages and deduplication during merge step."""
    transcript_file = Path(__file__).parent.parent / "transcripts_user" / "test_messy_150lines.txt"
    raw_text = transcript_file.read_text(encoding="utf-8")
    dialogue = parse_transcript_text(raw_text)

    # 1. Test chunking
    chunks = staged_chunk_dialogue(dialogue, chunk_size=35, overlap=5)
    assert len(chunks) >= 2, f"Expected at least 2 staged chunks, got {len(chunks)}"

    # 2. Test merge step deduplication
    chunk1_reqs = [
        Requirement(
            id="c1-1",
            transcript_id="chunk1",
            project_id="test_proj",
            description="Category taxonomy CSV bulk import with parent-child hierarchies",
            source_quote="Quote 1",
            priority="high",
        ),
        Requirement(
            id="c1-2",
            transcript_id="chunk1",
            project_id="test_proj",
            description="Lead routing and corporate email forwarders for attorney listings",
            source_quote="Quote 2",
            priority="high",
        ),
    ]

    chunk2_reqs = [
        # Duplicate of chunk1 intent
        Requirement(
            id="c2-1",
            transcript_id="chunk2",
            project_id="test_proj",
            description="Category taxonomy CSV bulk import with parent-child hierarchies",
            source_quote="Quote 1 repeat",
            priority="high",
        ),
        # New distinct requirement
        Requirement(
            id="c2-2",
            transcript_id="chunk2",
            project_id="test_proj",
            description="Google Maps search autocomplete and interactive directory map",
            source_quote="Quote 3",
            priority="high",
        ),
    ]

    merged, stats = merge_extracted_requirements([chunk1_reqs, chunk2_reqs], "test_transcript", "test_proj")

    assert stats["chunks_count"] == 2
    assert stats["total_candidate_statements"] == 4
    # The duplicate category CSV import should be merged, resulting in 3 unique requirements
    assert stats["merged_requirements_count"] == 3
    assert len(merged) == 3
    assert merged[0].id == "req-test_transcript-1"
    assert merged[1].id == "req-test_transcript-2"
    assert merged[2].id == "req-test_transcript-3"


@pytest.mark.asyncio
async def test_staged_chunking_and_merge_offline_pipeline(monkeypatch):
    """Chunking and merge test only on 150-line test transcript.
    
    NOTE: Processed via offline_heuristic fallback to avoid paid API calls.
    This test validates dialogue windowing and merge deduplication only;
    it is NOT an LLM long-transcript extraction evaluation.
    """
    from unittest.mock import MagicMock
    import agents.transcript_analyst as ta

    mock_llm = MagicMock()
    mock_llm.generate.side_effect = RuntimeError("Offline testing mode")
    monkeypatch.setattr(ta, "get_llm_client", lambda step=None: mock_llm)
    monkeypatch.setattr(settings, "allow_offline_fallback", True)

    transcript_file = Path(__file__).parent.parent / "transcripts_user" / "test_messy_150lines.txt"
    raw_text = transcript_file.read_text(encoding="utf-8")
    dialogue = parse_transcript_text(raw_text)

    # Staged extraction executes chunking and merging
    reqs = await extract_requirements_from_dialogue("test_messy_150lines", "proj_test_messy", dialogue)
    assert len(reqs) >= 4, f"Expected >= 4 requirements extracted, got {len(reqs)}"
    descs = " ".join(r.description.lower() for r in reqs)
    assert "category" in descs or "csv" in descs
    assert "email" in descs or "forward" in descs
    assert "maps" in descs or "google" in descs
