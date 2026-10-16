"""Tests for Knowledge Brain API routes via FastAPI test client."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


@pytest.mark.asyncio
async def test_health_endpoint():
    """GET /health should return 200 with status ok."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
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
