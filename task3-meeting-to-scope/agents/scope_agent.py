from __future__ import annotations

import uuid
from typing import List
from app.models import Requirement, ScopeDocument


def generate_scope_document(
    project_id: str,
    project_name: str,
    requirements: list[Requirement],
    target_date: str = "2026-11-15",
    version: int = 1,
) -> ScopeDocument:
    """Constructs comprehensive 10-section Scope of Work document based on validated requirements."""
    scope_id = f"scope-{project_id}-v{version}"

    # Generate deliverables from confirmed requirements
    deliverables = [
        f"Delivery and validation of: {req.description}"
        for req in requirements
        if req.status != "disputed"
    ]

    exclusions = [
        "Creation of new custom content, legal copywriting, or graphic design assets.",
        "Third-party subscription fees (e.g. Mailchimp, Twilio, Google Cloud API charges).",
        "Modifications to legacy core platform PHP source code outside supported widgets.",
    ]

    assumptions = [
        "Client provides valid administrator credentials and DNS access.",
        "Third-party vendor accounts (Stripe, Twilio, Google) are active and in good standing.",
        "Brilliant Directories solution center documentation accurately reflects live features.",
    ]

    acceptance_criteria = [
        "Category CSV imports successfully without parent-child taxonomy errors.",
        "Contact form inquiries forward cleanly to attorney corporate mailboxes.",
        "SSL certificate renders green padlock over HTTPS without mixed-content warnings.",
        "All features verified on desktop and mobile viewports.",
    ]

    client_duties = [
        "Provide final reviewed CSV taxonomy files 5 business days prior to milestone.",
        "Designate a single authorized point of contact for weekly progress reviews.",
        "Test and sign off on staging environment within 3 business days of deployment.",
    ]

    risks = [
        "DNS nameserver propagation delays may briefly postpone SSL generation.",
        "Large CSV imports may time out if row counts exceed server PHP execution limits.",
    ]

    # Detect if any requirements were extracted using offline heuristics
    is_offline = any(getattr(req, "extraction_mode", "llm") == "offline_heuristic" for req in requirements)
    extraction_mode = "offline_heuristic" if is_offline else "llm"
    init_status = "degraded_offline" if is_offline else "draft"

    return ScopeDocument(
        id=scope_id,
        project_id=project_id,
        version=version,
        title=f"Scope of Work — {project_name} (v{version})",
        objective=f"Implement and verify core platform improvements for {project_name}.",
        current_problem=(
            "The client has legacy or missing directory features causing manual overhead, "
            "missed client leads, and inconsistent member onboarding."
        ),
        agreed_requirements=requirements,
        proposed_solution=(
            "Deploy native Brilliant Directories configurations for category hierarchies, lead routing, "
            "and payment processing; integrate verified third-party webhooks for external workflows."
        ),
        deliverables=deliverables,
        exclusions=exclusions,
        assumptions_and_dependencies=assumptions,
        acceptance_criteria=acceptance_criteria,
        client_responsibilities=client_duties,
        open_questions_and_risks=risks,
        target_delivery_date=target_date,
        status=init_status,
        extraction_mode=extraction_mode,
    )
