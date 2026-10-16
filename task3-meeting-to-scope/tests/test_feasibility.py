import pytest
from app.models import Requirement
from agents.product_feasibility import check_requirement_feasibility


@pytest.mark.asyncio
async def test_check_requirement_feasibility_categories(monkeypatch):
    """When Task 1 returns answered for native feature, feasibility is existing_config."""
    from unittest.mock import MagicMock
    import httpx

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "answered",
        "answer": "Brilliant Directories supports bulk category upload via CSV in the Admin Portal.",
        "needs_human": False,
    }

    async def mock_post(*args, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    req = Requirement(
        id="r1",
        transcript_id="t1",
        project_id="p1",
        description="Import 4,000 categories via CSV file",
        source_quote="Import via CSV",
    )

    checked = await check_requirement_feasibility(req, timeout_seconds=1.0)
    assert checked.feasibility in ("existing_config", "existing_feature_with_limitation")
    assert checked.feasibility_detail != ""


@pytest.mark.asyncio
async def test_check_requirement_feasibility_custom_sms(monkeypatch):
    """When Task 1 returns answered with custom requirements, feasibility is potential_custom."""
    from unittest.mock import MagicMock
    import httpx

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "answered",
        "answer": "SMS 2FA is not natively supported. Requires custom webhook and Twilio integration.",
        "needs_human": False,
    }

    async def mock_post(*args, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    req = Requirement(
        id="r2",
        transcript_id="t1",
        project_id="p1",
        description="Integrate Twilio SMS 2FA verification for member registration",
        source_quote="Twilio SMS",
    )

    checked = await check_requirement_feasibility(req, timeout_seconds=1.0)
    assert checked.feasibility == "potential_custom"



@pytest.mark.asyncio
async def test_feasibility_status_error_labels_needs_clarification(monkeypatch):
    """When Task 1 returns status='error', feasibility must be 'needs_clarification'."""
    from unittest.mock import AsyncMock, MagicMock
    import httpx

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "error",
        "error_code": "LLM_UNAVAILABLE",
        "answer": "Knowledge service error: Gemini model unavailable",
        "needs_human": True,
    }

    async def mock_post(*args, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    req = Requirement(
        id="r3",
        transcript_id="t1",
        project_id="p1",
        description="Import 4,000 categories via CSV file",  # Has keywords that previously caused guessing
        source_quote="Import categories",
    )

    checked = await check_requirement_feasibility(req)
    assert checked.feasibility == "needs_clarification"
    assert "Pending clarification" in checked.existing_solution


@pytest.mark.asyncio
async def test_feasibility_insufficient_evidence_labels_needs_clarification(monkeypatch):
    """When Task 1 returns status='insufficient_evidence', feasibility must be 'needs_clarification'."""
    from unittest.mock import MagicMock
    import httpx

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "insufficient_evidence",
        "answer": "Not enough evidence found in documentation.",
        "needs_human": True,
    }

    async def mock_post(*args, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    req = Requirement(
        id="r4",
        transcript_id="t1",
        project_id="p1",
        description="Setup email forwarders with custom SPF records",
        source_quote="Email forwarders",
    )

    checked = await check_requirement_feasibility(req)
    assert checked.feasibility == "needs_clarification"


@pytest.mark.asyncio
async def test_feasibility_timeout_labels_needs_clarification_never_guesses(monkeypatch):
    """When Task 1 times out or raises an error, feasibility must be 'needs_clarification' (no keyword guessing)."""
    import httpx

    async def mock_timeout(*args, **kwargs):
        raise httpx.TimeoutException("Connection timed out after 500ms")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_timeout)

    # Even with strong keywords like 'csv', 'categories', 'stripe', it must NEVER guess native or custom!
    req = Requirement(
        id="r5",
        transcript_id="t1",
        project_id="p1",
        description="Import 4,000 categories via CSV and configure Stripe payment gateway",
        source_quote="CSV categories Stripe",
    )

    checked = await check_requirement_feasibility(req)
    assert checked.feasibility == "needs_clarification"
    assert "timed out" in checked.feasibility_detail.lower() or "unavailable" in checked.feasibility_detail.lower()


@pytest.mark.asyncio
async def test_feasibility_quota_exhausted_labels_needs_clarification(monkeypatch):
    """When Task 1 returns QUOTA_EXHAUSTED, feasibility must be 'needs_clarification' and mention code."""
    from unittest.mock import MagicMock
    import httpx

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "error",
        "error_code": "QUOTA_EXHAUSTED",
        "answer": "Gemini daily quota exhausted: 429 RESOURCE_EXHAUSTED",
        "needs_human": True,
    }

    async def mock_post(*args, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    req = Requirement(
        id="r-quota",
        transcript_id="t1",
        project_id="p1",
        description="Configure automated invoice generation",
        source_quote="Automated invoices",
    )

    checked = await check_requirement_feasibility(req)
    assert checked.feasibility == "needs_clarification"
    assert "QUOTA_EXHAUSTED" in checked.feasibility_detail


@pytest.mark.asyncio
async def test_feasibility_rate_limited_labels_needs_clarification(monkeypatch):
    """When Task 1 returns RATE_LIMITED, feasibility must be 'needs_clarification' and mention code."""
    from unittest.mock import MagicMock
    import httpx

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "error",
        "error_code": "RATE_LIMITED",
        "answer": "Rate limit exceeded (15 RPM).",
        "needs_human": True,
    }

    async def mock_post(*args, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    req = Requirement(
        id="r-rate",
        transcript_id="t1",
        project_id="p1",
        description="Setup custom directory webhooks",
        source_quote="Custom webhooks",
    )

    checked = await check_requirement_feasibility(req)
    assert checked.feasibility == "needs_clarification"
    assert "RATE_LIMITED" in checked.feasibility_detail


@pytest.mark.asyncio
async def test_feasibility_invalid_output_labels_needs_clarification(monkeypatch):
    """When Task 1 returns INVALID_OUTPUT, feasibility must be 'needs_clarification' and mention code."""
    from unittest.mock import MagicMock
    import httpx

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "error",
        "error_code": "INVALID_OUTPUT",
        "answer": "Failed to parse structured JSON response from model.",
        "needs_human": True,
    }

    async def mock_post(*args, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    req = Requirement(
        id="r-invalid",
        transcript_id="t1",
        project_id="p1",
        description="Verify third-party single sign-on",
        source_quote="Single sign-on",
    )

    checked = await check_requirement_feasibility(req)
    assert checked.feasibility == "needs_clarification"
    assert "INVALID_OUTPUT" in checked.feasibility_detail

