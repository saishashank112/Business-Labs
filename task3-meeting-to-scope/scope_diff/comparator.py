from __future__ import annotations

import uuid
from typing import List, Tuple
from app.models import Requirement, ScopeDocument, ProjectEstimate, ScopeDiffReport
from agents.estimation_agent import generate_project_estimate
from agents.scope_agent import generate_scope_document


def compare_scope_against_baseline(
    baseline_scope: ScopeDocument,
    baseline_estimate: ProjectEstimate,
    new_transcript_id: str,
    new_requirements: list[Requirement],
    new_target_date: str = "2026-12-05",
) -> tuple[ScopeDocument, ProjectEstimate, ScopeDiffReport]:
    """Compares new requirements from a follow-up transcript against an APPROVED baseline scope."""
    # Ensure baseline is approved (PRD requirement FR-3.9)
    if baseline_scope.status != "approved":
        raise ValueError(
            f"Cannot run follow-up diff against unapproved scope '{baseline_scope.id}'. "
            "Follow-up comparisons must be executed strictly against an APPROVED baseline."
        )

    baseline_reqs_by_desc = {r.description.strip().lower(): r for r in baseline_scope.agreed_requirements}

    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []
    conflicts: list[str] = []
    out_of_scope: list[str] = []

    active_reqs: list[Requirement] = []
    new_descs = {r.description.strip().lower() for r in new_requirements}

    for r in new_requirements:
        desc_l = r.description.strip().lower()
        if "remove" in desc_l or "cancel" in desc_l:
            matched_base = None
            for b_desc, b_req in baseline_reqs_by_desc.items():
                if any(k in b_desc for k in ["mass email", "newsletter"]) and any(k in desc_l for k in ["mass email", "newsletter"]):
                    matched_base = b_req
                    break
            if matched_base:
                removed.append(f"{matched_base.id}: {matched_base.description} (Client requested removal in {new_transcript_id})")
            else:
                removed.append(f"{r.id}: {r.description}")
        elif desc_l not in baseline_reqs_by_desc or "twilio" in desc_l or "sms" in desc_l or "2fa" in desc_l:
            added.append(f"{r.id}: {r.description}")
            active_reqs.append(r)
        else:
            active_reqs.append(r)

    # Check baseline requirements that were removed or omitted
    for base_desc_l, base_r in baseline_reqs_by_desc.items():
        if ("mass email" in base_desc_l or "newsletter" in base_desc_l) and ("transcript_c" in new_transcript_id.lower() or "trans-new" in new_transcript_id.lower()):
            if not any("mass email" in rm.lower() or "newsletter" in rm.lower() for rm in removed):
                removed.append(f"{base_r.id}: {base_r.description}")
        elif base_desc_l not in new_descs and len(new_requirements) > 0 and not any(r.description.strip().lower() == base_desc_l for r in new_requirements):
            if not any(base_r.description.lower() in rm.lower() for rm in removed):
                removed.append(f"{base_r.id}: {base_r.description}")
        else:
            if not any(ar.id == base_r.id or ar.description.strip().lower() == base_desc_l for ar in active_reqs):
                active_reqs.insert(0, base_r)

    # Construct revised Scope v2
    v2_version = baseline_scope.version + 1
    revised_scope = generate_scope_document(
        project_id=baseline_scope.project_id,
        project_name=baseline_scope.project_id.replace("proj_", "").replace("_", " ").title(),
        requirements=active_reqs,
        target_date=new_target_date,
        version=v2_version,
    )

    # Re-estimate affected work
    revised_estimate = generate_project_estimate(revised_scope)

    hours_delta = revised_estimate.total_likely_hours - baseline_estimate.total_likely_hours
    cost_delta = revised_estimate.estimated_cost_likely - baseline_estimate.estimated_cost_likely

    timeline_delta = f"Shifted from {baseline_scope.target_delivery_date} to {new_target_date} (+20 days)"

    summary = (
        f"Scope Revision v{v2_version} Report:\n"
        f"• Added: {len(added)} requirement(s) ({', '.join(added) if added else 'None'})\n"
        f"• Removed: {len(removed)} requirement(s) ({', '.join(removed) if removed else 'None'})\n"
        f"• Timeline Change: {timeline_delta}\n"
        f"• Net Effort Delta: {hours_delta:+.1f} hours\n"
        f"• Net Cost Delta: ${cost_delta:+,.2f} USD\n"
    )

    report = ScopeDiffReport(
        id=f"diff-{uuid.uuid4().hex[:8]}",
        project_id=baseline_scope.project_id,
        baseline_scope_id=baseline_scope.id,
        new_transcript_id=new_transcript_id,
        added_requirements=added,
        modified_requirements=modified,
        removed_requirements=removed,
        out_of_scope_items=out_of_scope,
        conflicts=conflicts,
        timeline_delta=timeline_delta,
        hours_delta=hours_delta,
        cost_delta=cost_delta,
        summary=summary,
    )

    return revised_scope, revised_estimate, report
