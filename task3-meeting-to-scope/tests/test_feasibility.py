import pytest
from app.models import Requirement
from agents.product_feasibility import check_requirement_feasibility


@pytest.mark.asyncio
async def test_check_requirement_feasibility_categories():
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
async def test_check_requirement_feasibility_custom_sms():
    req = Requirement(
        id="r2",
        transcript_id="t1",
        project_id="p1",
        description="Integrate Twilio SMS 2FA verification for member registration",
        source_quote="Twilio SMS",
    )

    checked = await check_requirement_feasibility(req, timeout_seconds=1.0)
    assert checked.feasibility in ("potential_custom", "needs_clarification")
