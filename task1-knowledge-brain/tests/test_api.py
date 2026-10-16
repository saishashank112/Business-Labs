import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.database import init_db


@pytest.mark.asyncio
async def test_health_endpoint():
    """GET /health should return 200 with status ok."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert data["db"] == "connected"
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_query_rejects_missing_api_key():
    """POST /query without X-API-Key should be rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/query", json={"question": "How to add PayPal?"})
    # FastAPI returns 422 for missing required header
    assert response.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_query_rejects_invalid_api_key():
    """POST /query with wrong X-API-Key should return 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/query",
            json={"question": "How to add PayPal?"},
            headers={"X-API-Key": "wrong-key"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_query_success_with_valid_api_key():
    """POST /query with valid X-API-Key should return 200 and propagate request ID."""
    await init_db()
    custom_request_id = "test-req-id-12345"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/query",
            json={"question": "What is Brilliant Directories?", "mode": "keyword"},
            headers={
                "X-API-Key": settings.t1_api_key,
                "X-Request-Id": custom_request_id,
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "status" in data
    assert "sources" in data
    assert response.headers.get("X-Request-Id") == custom_request_id
    assert data["request_id"] == custom_request_id


@pytest.mark.asyncio
async def test_startup_fails_if_t1_api_key_is_default(monkeypatch):
    from app.main import lifespan
    monkeypatch.setattr(settings, "t1_api_key", "change-me-in-production")
    with pytest.raises(RuntimeError, match="CRITICAL SECURITY CONFIG ERROR"):
        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_startup_fails_if_t1_api_key_is_empty(monkeypatch):
    from app.main import lifespan
    monkeypatch.setattr(settings, "t1_api_key", "")
    with pytest.raises(RuntimeError, match="CRITICAL SECURITY CONFIG ERROR"):
        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_startup_refuses_final_profile_with_empty_claude_ids(monkeypatch):
    from app.main import lifespan
    monkeypatch.setattr(settings, "t1_api_key", "valid-key-12345")
    monkeypatch.setattr(settings, "profile", "final")
    monkeypatch.setattr(settings, "claude_model_fast", "")
    with pytest.raises(RuntimeError, match="Final profile requires CLAUDE_MODEL_FAST"):
        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_no_test_data_leak_in_real_task1_db():
    """Verify that Task 1 tests run against an isolated temporary database, not real task1.db."""
    from pathlib import Path

    assert "task1_test.db" in settings.t1_db_path
