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

            if status == "insufficient_evidence" or data.get("needs_human"):
                requirement.feasibility = "needs_clarification"
                requirement.feasibility_detail = (
                    "Knowledge Brain found no conclusive evidence. Flagged for human technical review."
                )
            elif "custom" in lower_ans or "not natively supported" in lower_ans or "webhook" in lower_ans:
                requirement.feasibility = "potential_custom"
                requirement.feasibility_detail = answer[:250]
            elif "external" in lower_ans or "limitation" in lower_ans or "third-party" in lower_ans:
                requirement.feasibility = "existing_feature_with_limitation"
                requirement.feasibility_detail = answer[:250]
            else:
                requirement.feasibility = "existing_config"
                requirement.feasibility_detail = answer[:250]

            requirement.existing_solution = answer[:200]
        else:
            requirement.feasibility = "needs_clarification"
            requirement.feasibility_detail = f"Task 1 HTTP error ({resp.status_code}). Human verification needed."
    except Exception as e:
        logger.warning("Failed to connect to Task 1 Knowledge Brain: %s", e)
        # Rule-based fallback based on keywords if Task 1 server is offline
        desc_lower = requirement.description.lower()
        if "category" in desc_lower or "csv" in desc_lower or "email forwarder" in desc_lower or "ssl" in desc_lower or "social" in desc_lower or "stripe" in desc_lower or "map" in desc_lower or "google" in desc_lower:
            requirement.feasibility = "existing_config"
            requirement.feasibility_detail = "Supported via native Brilliant Directories admin configuration."
        elif "mass email" in desc_lower or "campaign" in desc_lower:
            requirement.feasibility = "existing_feature_with_limitation"
            requirement.feasibility_detail = "Native email tool has volume caps; recommends external SendGrid/Mailchimp integration."
        elif "2fa" in desc_lower or "sms" in desc_lower or "twilio" in desc_lower:
            requirement.feasibility = "potential_custom"
            requirement.feasibility_detail = "Requires custom webhook or API integration with third-party SMS provider."
        else:
            requirement.feasibility = "needs_clarification"
            requirement.feasibility_detail = "Knowledge service offline. Flagged for human review."

    return requirement
