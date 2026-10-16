import pytest
from agents.transcript_analyst import extract_requirements_from_dialogue


@pytest.mark.asyncio
async def test_extract_requirements_from_dialogue():
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
