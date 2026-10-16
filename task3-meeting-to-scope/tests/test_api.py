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
async def test_analyze_transcript_a_and_approve():
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
        assert comp_data["revised_scope"]["version"] == 2
