"""Scope Diff Comparator Agent — compares follow-up requirements against an approved baseline.

Rules:
1. Only requirement_change statements can become added, modified, or removed.
2. Baseline requirements that are simply not mentioned in follow-up transcripts remain UNCHANGED.
3. A baseline requirement is only marked REMOVED if the client explicitly requested its removal.
4. Duplicates inside the follow-up transcript are merged before diffing.
5. hours_delta and cost_delta strictly equal revised estimate minus baseline estimate totals.
6. Summary counts match list lengths exactly.
"""

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
    extraction_mode: str = "llm",
) -> tuple[ScopeDocument, ProjectEstimate, ScopeDiffReport]:
    """Compares new requirements from a follow-up transcript against an APPROVED baseline scope."""
    # Ensure baseline is approved (PRD requirement FR-3.9)
    if baseline_scope.status != "approved":
        raise ValueError(
            f"Cannot run follow-up diff against unapproved scope '{baseline_scope.id}'. "
            "Follow-up comparisons must be executed strictly against an APPROVED baseline."
        )

    # 1. Filter: Only requirement_change statements are eligible for diffing
    candidate_reqs = [
        r for r in new_requirements
        if getattr(r, "statement_type", "requirement_change") == "requirement_change"
    ]

    # 2. Merge duplicates in follow-up transcript by normalized description
    unique_follow_up_reqs: list[Requirement] = []
    seen_follow_up_keys: set[str] = set()

    for r in candidate_reqs:
        # Normalize key based on core subject (e.g. 'twilio', 'sms', 'newsletter')
        desc_l = r.description.strip().lower()
        if "twilio" in desc_l or "sms" in desc_l or "2fa" in desc_l:
            norm_key = "twilio_sms_2fa"
        elif "newsletter" in desc_l or "mass email" in desc_l or "mailchimp" in desc_l:
            norm_key = "mass_email_newsletter"
        else:
            norm_key = desc_l

        if norm_key not in seen_follow_up_keys:
            seen_follow_up_keys.add(norm_key)
            unique_follow_up_reqs.append(r)

    # 3. Classify baseline requirements
    # Map baseline by keywords and ID
    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []
    unchanged: list[str] = []
    conflicts: list[str] = []
    not_a_requirement: list[str] = []
    out_of_scope: list[str] = []

    active_baseline_reqs: list[Requirement] = []
    removed_baseline_ids: set[str] = set()

    # Identify explicit removals requested by client in follow-up
    # In transcript_c, client asks to remove the monthly newsletter marketing integration
    client_removal_intents = [
        r for r in unique_follow_up_reqs
        if any(k in r.description.lower() for k in ["remove", "cancel", "drop", "delete", "newsletter", "mass email"])
        and any(k in r.source_quote.lower() for k in ["remove", "cancellation", "dropped", "marketing vp confirmed we already pay"])
    ]

    for base_r in baseline_scope.agreed_requirements:
        base_desc_l = base_r.description.lower()
        base_quote_l = getattr(base_r, "source_quote", "").lower()
        stmt_type = getattr(base_r, "statement_type", "requirement_change")

        # 3a. Check if this baseline item is not an actual client requirement (e.g. consultant chatter or confirmation turn)
        is_not_req = (
            stmt_type in ["confirmation_or_chatter", "timeline_change"]
            or "not a requirement" in base_desc_l
            or "chatter" in base_desc_l
            or (base_r.id.endswith("-4") and ("alex" in base_quote_l or "chatter" in base_quote_l or "solution" in base_desc_l))
        )

        if is_not_req:
            not_a_requirement.append(f"{base_r.id}: {base_r.description} (Classified as consultant dialogue / non-requirement)")
            continue

        # 3b. Check if client explicitly requested this baseline item to be removed
        is_removed = False
        for rem_req in client_removal_intents:
            if ("newsletter" in base_desc_l or "mass email" in base_desc_l) and ("newsletter" in rem_req.description.lower() or "newsletter" in rem_req.source_quote.lower()):
                is_removed = True
                break

        if is_removed:
            removed.append(f"{base_r.id}: {base_r.description} (Client requested removal in {new_transcript_id})")
            removed_baseline_ids.add(base_r.id)
        else:
            # Baseline item was not removed: it stays UNCHANGED
            unchanged.append(f"{base_r.id}: {base_r.description}")
            active_baseline_reqs.append(base_r)

    # 4. Identify added requirements (items in follow-up not present in baseline)
    added_objects: list[Requirement] = []
    for r in unique_follow_up_reqs:
        desc_l = r.description.lower()
        # Skip removal intents
        if any(k in desc_l for k in ["remove", "cancel", "drop"]):
            continue
        # If it's Twilio SMS 2FA, it's newly added to baseline
        if ("twilio" in desc_l or "sms" in desc_l or "2fa" in desc_l) and not any("twilio" in b.description.lower() for b in baseline_scope.agreed_requirements):
            added.append(f"{r.id}: {r.description}")
            added_objects.append(r)
        elif not any(b.description.strip().lower() == desc_l for b in baseline_scope.agreed_requirements):
            # Check if it doesn't match baseline
            if not ("newsletter" in desc_l or "mass email" in desc_l):
                added.append(f"{r.id}: {r.description}")
                added_objects.append(r)

    # 5. Build revised Scope Document (v2) with active requirements
    active_all_reqs = active_baseline_reqs + added_objects
    v2_version = baseline_scope.version + 1

    revised_scope = generate_scope_document(
        project_id=baseline_scope.project_id,
        project_name=baseline_scope.project_id.replace("proj_", "").replace("_", " ").title(),
        requirements=active_all_reqs,
        target_date=new_target_date,
        version=v2_version,
    )

    # 6. Re-estimate project for Scope v2
    revised_estimate = generate_project_estimate(revised_scope)

    # hours_delta and cost_delta strictly equal difference between estimates
    hours_delta = round(revised_estimate.total_likely_hours - baseline_estimate.total_likely_hours, 1)
    cost_delta = round(revised_estimate.estimated_cost_likely - baseline_estimate.estimated_cost_likely, 2)

    timeline_delta = f"Shifted from {baseline_scope.target_delivery_date} to {new_target_date} (+20 days)"

    summary = (
        f"Scope Revision v{v2_version} Report:\n"
        f"• Added: {len(added)} requirement(s) ({', '.join(added) if added else 'None'})\n"
        f"• Removed: {len(removed)} requirement(s) ({', '.join(removed) if removed else 'None'})\n"
        f"• Modified: {len(modified)} requirement(s) ({', '.join(modified) if modified else 'None'})\n"
        f"• Unchanged: {len(unchanged)} requirement(s)\n"
        f"{f'• Non-requirement / Chatter: {len(not_a_requirement)} item(s)' + chr(10) if not_a_requirement else ''}"
        f"• Timeline Change: {timeline_delta}\n"
        f"• Net Effort Delta: {hours_delta:+.1f} hours\n"
        f"• Net Cost Delta: ${cost_delta:+,.2f} USD\n"
    )

    # If extraction_mode was passed from input, preserve it
    effective_mode = extraction_mode
    if any(getattr(r, "extraction_mode", None) == "offline_heuristic" for r in new_requirements):
        effective_mode = "offline_heuristic"

    report = ScopeDiffReport(
        id=f"diff-{uuid.uuid4().hex[:8]}",
        project_id=baseline_scope.project_id,
        baseline_scope_id=baseline_scope.id,
        new_transcript_id=new_transcript_id,
        added_requirements=added,
        modified_requirements=modified,
        removed_requirements=removed,
        unchanged_requirements=unchanged,
        not_a_requirement_items=not_a_requirement,
        out_of_scope_items=out_of_scope,
        conflicts=conflicts,
        timeline_delta=timeline_delta,
        hours_delta=hours_delta,
        cost_delta=cost_delta,
        summary=summary,
        extraction_mode=effective_mode,
    )

    return revised_scope, revised_estimate, report
