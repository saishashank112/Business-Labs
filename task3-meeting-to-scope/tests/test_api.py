import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "task3-meeting-to-scope"


@pytest.mark.asyncio
async def test_list_transcripts():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/transcripts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    labels = [t["label"] for t in data]
    assert "A" in labels
    assert "B" in labels
    assert "C" in labels


@pytest.mark.asyncio
async def test_analyze_transcript_a_and_approve(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from agents.transcript_analyst import ExtractedStatementList, ExtractedStatement
    from llm.interface import LLMResponse
    import agents.transcript_analyst as ta

    def mock_get_llm(step=None):
        mock_llm = MagicMock()
        async def mock_generate(prompt, **kwargs):
            if "transcript_c" in prompt or "TRANSCRIPT ID: transcript_c" in prompt:
                stmts = [
                    ExtractedStatement(
                        speaker="Emily Watson",
                        short_description="Twilio SMS 2FA integration for attorney registration and profile management",
                        source_quote="First, our security compliance committee has mandated two-factor authentication. We want to ADD an SMS two-factor verification requirement using Twilio when attorneys register or edit their profile credentials.",
                        statement_type="requirement_change",
                        change_intent="add",
                        priority="high",
                    ),
                    ExtractedStatement(
                        speaker="Alex Rivera",
                        short_description="Confirmation chatter",
                        source_quote="Got it. That is an ADDED requirement...",
                        statement_type="confirmation_or_chatter",
                        change_intent="none",
                        priority="medium",
                    ),
                    ExtractedStatement(
                        speaker="Emily Watson",
                        short_description="Monthly legal newsletter campaign broadcast",
                        source_quote="We have decided to REMOVE the mass email marketing integration from your scope entirely...",
                        statement_type="requirement_change",
                        change_intent="remove",
                        priority="medium",
                    ),
                    ExtractedStatement(
                        speaker="Emily Watson",
                        short_description="Delivery milestone change",
                        source_quote="Can we move the final delivery milestone from November 15 to December 5, 2026?",
                        statement_type="timeline_change",
                        change_intent="modify",
                        priority="medium",
                    ),
                ]
            else:
                stmts = [
                    ExtractedStatement(
                        speaker="Emily Watson",
                        short_description="Category taxonomy CSV bulk import with parent-child hierarchies",
                        source_quote="Our first key requirement is importing our complete category taxonomy via CSV...",
                        statement_type="requirement_change",
                        change_intent="add",
                        priority="high",
                    ),
                    ExtractedStatement(
                        speaker="Emily Watson",
                        short_description="Lead routing and corporate email forwarders for attorney listings",
                        source_quote="Second, when a potential client visits an attorney's listing and fills out the contact form...",
                        statement_type="requirement_change",
                        change_intent="add",
                        priority="high",
                    ),
                    ExtractedStatement(
                        speaker="Emily Watson",
                        short_description="Monthly legal newsletter campaign broadcast via third-party email provider",
                        source_quote="Third, we want to broadcast a monthly legal newsletter to all 4,000 attorneys...",
                        statement_type="requirement_change",
                        change_intent="add",
                        priority="medium",
                    ),
                    ExtractedStatement(
                        speaker="Emily Watson",
                        short_description="Google Maps search autocomplete and interactive radius directory map",
                        source_quote="Fourth requirement: On our homepage, visitors must be able to type a city or zip code...",
                        statement_type="requirement_change",
                        change_intent="add",
                        priority="high",
                    ),
                    ExtractedStatement(
                        speaker="Emily Watson",
                        short_description="Remote administrative staff training (5 hours dedicated)",
                        source_quote="Lastly, our team needs 5 hours of remote staff training on managing member listings...",
                        statement_type="requirement_change",
                        change_intent="add",
                        priority="medium",
                    ),
                ]
            return LLMResponse(
                text="{}",
                parsed=ExtractedStatementList(statements=stmts),
                input_tokens=100,
                output_tokens=50,
                latency_ms=100,
                model="mock-gemini",
                provider="gemini",
            )
        mock_llm.generate = mock_generate
        return mock_llm

    monkeypatch.setattr(ta, "get_llm_client", mock_get_llm)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Run 5-agent pipeline on transcript A
        resp = await ac.post("/api/transcripts/transcript_a/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["requirements"]) >= 4
        assert data["scope"]["id"] is not None
        assert data["estimate"]["total_likely_hours"] > 0
        assert data["proposal"]["title"] is not None

        scope_id = data["scope"]["id"]
        project_id = data["project_id"]

        # Formally approve baseline scope
        appr_resp = await ac.post(
            f"/api/projects/{project_id}/approve",
            json={"scope_version_id": scope_id, "reviewer": "Emily Watson, Managing Director"},
        )
        assert appr_resp.status_code == 200
        assert appr_resp.json()["success"] is True

        # Now test compare endpoint against the approved baseline
        comp_resp = await ac.post(
            f"/api/projects/{project_id}/compare",
            json={"baseline_scope_id": scope_id, "follow_up_transcript_id": "transcript_c"},
        )
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert comp_data["success"] is True
        assert len(comp_data["diff_report"]["added_requirements"]) >= 1
        assert len(comp_data["diff_report"]["removed_requirements"]) >= 1

