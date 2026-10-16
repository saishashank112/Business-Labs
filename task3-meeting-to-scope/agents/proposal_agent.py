from __future__ import annotations

import uuid
from app.models import ScopeDocument, ProjectEstimate, ProposalDocument


def generate_proposal_document(
    scope: ScopeDocument,
    estimate: ProjectEstimate,
) -> ProposalDocument:
    """Drafts client-ready technical proposal tightly aligned with scope and estimates."""
    proposal_id = f"prop-{scope.id}"

    exec_summary = (
        f"This proposal outlines the technical engagement for {scope.title}. "
        f"Our team will deliver {len(scope.deliverables)} core milestones, targeting completion by "
        f"{scope.target_delivery_date}."
    )

    pricing_breakdown = (
        f"Estimated Effort: {estimate.total_likely_hours:.1f} hours "
        f"(Range: {estimate.total_low_hours:.1f}h - {estimate.total_high_hours:.1f}h)\n"
        f"Hourly Rate: {estimate.currency} ${estimate.hourly_rate:.2f}/hr\n"
        f"Estimated Total: {estimate.currency} ${estimate.estimated_cost_likely:,.2f} "
        f"(Range: ${estimate.estimated_cost_low:,.2f} - ${estimate.estimated_cost_high:,.2f})\n\n"
        f"Note: Hours represent an engineering estimate based on documented requirements, not a fixed-price bid."
    )

    return ProposalDocument(
        id=proposal_id,
        project_id=scope.project_id,
        scope_version_id=scope.id,
        estimate_id=estimate.id,
        title=f"Technical Project Proposal — {scope.title}",
        executive_summary=exec_summary,
        problem_and_solution=f"Problem:\n{scope.current_problem}\n\nSolution:\n{scope.proposed_solution}",
        scope_summary="\n".join([f"- {d}" for d in scope.deliverables]),
        timeline=f"Target Completion Milestone: {scope.target_delivery_date}",
        pricing_breakdown=pricing_breakdown,
        client_duties=scope.client_responsibilities,
        exclusions=scope.exclusions,
        risks_and_mitigations=scope.open_questions_and_risks,
        next_steps=[
            "1. Client review and sign-off on Scope of Work baseline.",
            "2. Provisioning of administrator access credentials and API tokens.",
            "3. Engineering kickoff and staging environment configuration.",
        ],
        status="draft",
    )
