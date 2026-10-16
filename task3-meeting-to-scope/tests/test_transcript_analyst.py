import pytest
from unittest.mock import AsyncMock, MagicMock
from agents.transcript_analyst import (
    extract_requirements_from_dialogue,
    ExtractedStatementList,
    ExtractedStatement,
)
from llm.interface import LLMResponse


@pytest.mark.asyncio
async def test_extract_requirements_from_dialogue(monkeypatch):
    mock_statements = ExtractedStatementList(
        statements=[
            ExtractedStatement(
                speaker="Emily Watson",
                short_description="Import category taxonomy via CSV file",
                source_quote='"Our first key requirement is importing our complete category taxonomy via CSV file." (Emily Watson at 00:01:00)',
                statement_type="requirement_change",
                priority="high",
            ),
            ExtractedStatement(
                speaker="Emily Watson",
                short_description="Email forwarders for attorney listings",
                source_quote='"Second, we need email forwarders configured so inquiries route directly to attorneys." (Emily Watson at 00:02:00)',
                statement_type="requirement_change",
                priority="high",
            ),
        ]
    )

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResponse(
            text="{}",
            parsed=mock_statements,
            input_tokens=100,
            output_tokens=50,
            latency_ms=100,
            model="mock-gemini",
            provider="gemini",
        )
    )

    import agents.transcript_analyst as ta
    monkeypatch.setattr(ta, "get_llm_client", lambda step=None: mock_llm)

    dialogue = [
        {
            "timestamp": "00:01:00",
            "speaker": "Emily Watson",
            "text": "Our first key requirement is importing our complete category taxonomy via CSV file.",
        },
        {
            "timestamp": "00:02:00",
            "speaker": "Emily Watson",
            "text": "Second, we need email forwarders configured so inquiries route directly to attorneys.",
        },
    ]

    reqs = await extract_requirements_from_dialogue("test_transcript", "test_proj", dialogue)
    assert len(reqs) == 2
    assert "category" in reqs[0].description.lower() or "csv" in reqs[0].description.lower()
    assert "Emily Watson" in reqs[0].source_quote
    assert reqs[0].transcript_id == "test_transcript"
    assert reqs[0].status == "confirmed"

