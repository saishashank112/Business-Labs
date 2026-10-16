from __future__ import annotations

import httpx
import logging
from typing import Optional
from app.config import settings
from app.models import Requirement

logger = logging.getLogger(__name__)


async def check_requirement_feasibility(
    requirement: Requirement,
    timeout_seconds: float = 0.5,
) -> Requirement:
    """Queries Task 1 Knowledge Brain API via HTTP to verify platform feasibility."""
    url = f"{settings.t1_base_url}/query"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": settings.t1_api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={"question": requirement.description, "mode": "hybrid"},
            )

        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("answer", "")
            status = data.get("status", "")
            lower_ans = answer.lower()

            if status in ("error", "insufficient_evidence") or data.get("needs_human"):
                err_code = data.get("error_code")
                requirement.feasibility = "needs_clarification"
                requirement.feasibility_detail = (
                    f"Knowledge Brain {status} [{err_code}]: {answer}" if err_code else (answer or "Insufficient evidence or service error.")
                )
                requirement.existing_solution = "Pending clarification from technical documentation."
            elif "custom" in lower_ans or "not natively supported" in lower_ans or "webhook" in lower_ans:
                requirement.feasibility = "potential_custom"
                requirement.feasibility_detail = answer[:250]
                requirement.existing_solution = answer[:200]
            elif "external" in lower_ans or "limitation" in lower_ans or "third-party" in lower_ans:
                requirement.feasibility = "existing_feature_with_limitation"
                requirement.feasibility_detail = answer[:250]
                requirement.existing_solution = answer[:200]
            else:
                requirement.feasibility = "existing_config"
                requirement.feasibility_detail = answer[:250]
                requirement.existing_solution = answer[:200]
        else:
            requirement.feasibility = "needs_clarification"
            requirement.feasibility_detail = f"Task 1 HTTP error ({resp.status_code}). Human verification needed."
            requirement.existing_solution = "Pending clarification due to service error."
    except Exception as e:
        logger.warning("Failed to connect to Task 1 Knowledge Brain (%s): %s", type(e).__name__, e)
        # On timeout, connection error, or service unavailability, never guess. Always label needs_clarification.
        requirement.feasibility = "needs_clarification"
        requirement.feasibility_detail = (
            f"Knowledge service unavailable or timed out ({type(e).__name__}). Flagged for human technical review."
        )
        requirement.existing_solution = "Pending clarification from technical documentation."

    return requirement
