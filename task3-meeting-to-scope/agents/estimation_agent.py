from __future__ import annotations

import uuid
from typing import List
from app.config import settings
from app.models import Requirement, ScopeDocument, EstimateTask, ProjectEstimate


def generate_project_estimate(
    scope: ScopeDocument,
    hourly_rate: float = settings.t3_hourly_rate,
    currency: str = settings.t3_currency,
) -> ProjectEstimate:
    """Generates transparent low/likely/high hour estimates and pricing per requirement."""
    tasks: list[EstimateTask] = []

    for req in scope.agreed_requirements:
        desc = req.description.lower()

        # Calibrated baseline engineering estimates based on feasibility
        if "category" in desc or "csv" in desc:
            low, likely, high = 4.0, 6.0, 10.0
            reason = "CSV taxonomy validation, formatting hierarchy columns, test upload, and rollback verification."
        elif "forwarder" in desc or "email" in desc and "mass" not in desc:
            low, likely, high = 3.0, 4.0, 6.0
            reason = "Email accounts creation, DNS MX/SPF verification, lead routing configuration, and delivery testing."
        elif "mass email" in desc or "mailchimp" in desc or "sendgrid" in desc:
            low, likely, high = 6.0, 8.0, 12.0
            reason = "Third-party transactional API setup, contact sync webhooks, template testing, and bounce handling."
        elif "maps" in desc or "google" in desc or "radius" in desc:
            low, likely, high = 3.0, 5.0, 8.0
            reason = "Google Cloud Console API key restriction, billing enablement, geocoding testing on search widget."
        elif "training" in desc or "staff" in desc:
            low, likely, high = 5.0, 5.0, 6.0
            reason = "5 hours dedicated remote training session plus recorded walkthrough and Q&A documentation."
        elif "stripe" in desc or "payment" in desc:
            low, likely, high = 4.0, 6.0, 9.0
            reason = "Stripe webhook setup, subscription product tiers, test mode transactions, and live gateway activation."
        elif "ssl" in desc or "https" in desc:
            low, likely, high = 2.0, 3.0, 4.0
            reason = "DNS nameserver verification, Let's Encrypt certificate installation, and HTTP to HTTPS redirects."
        elif "twilio" in desc or "sms" in desc or "2fa" in desc:
            low, likely, high = 8.0, 12.0, 18.0
            reason = "Custom Twilio REST API integration, verification code generation, session management, and rate limiting."
        else:
            low, likely, high = 3.0, 5.0, 8.0
            reason = "Platform configuration, UI testing, and documentation."

        tasks.append(
            EstimateTask(
                name=f"Implementation: {req.description[:60]}",
                requirement_id=req.id,
                low_hours=low,
                likely_hours=likely,
                high_hours=high,
                reasoning=reason,
                assumptions="Assumes client provides required credentials in a timely manner.",
                dependencies=req.dependencies,
            )
        )

    tot_low = sum(t.low_hours for t in tasks)
    tot_likely = sum(t.likely_hours for t in tasks)
    tot_high = sum(t.high_hours for t in tasks)

    return ProjectEstimate(
        id=f"est-{scope.id}",
        scope_version_id=scope.id,
        project_id=scope.project_id,
        tasks=tasks,
        total_low_hours=tot_low,
        total_likely_hours=tot_likely,
        total_high_hours=tot_high,
        hourly_rate=hourly_rate,
        currency=currency,
        estimated_cost_low=tot_low * hourly_rate,
        estimated_cost_likely=tot_likely * hourly_rate,
        estimated_cost_high=tot_high * hourly_rate,
        version=scope.version,
    )
