"""Tests for Scope Diff Comparator.

Verifies strict approval gating, 4-way statement classification, unchanged baseline retention,
duplicate merging, exact timeline deltas, and hours/cost calculations without external model calls.
"""

import json
from pathlib import Path
import pytest
from app.models import Requirement, ScopeDocument, ProjectEstimate
from agents.scope_agent import generate_scope_document
from agents.estimation_agent import generate_project_estimate
from scope_diff.comparator import compare_scope_against_baseline


def test_scope_diff_rejects_unapproved_baseline():
    """Gating test: follow-up comparison MUST fail if baseline is unapproved."""
    req1 = Requirement(id="r1", transcript_id="tA", project_id="p1", description="CSV import", source_quote="quote")
    unapproved_scope = generate_scope_document("p1", "Test Project", [req1])
    unapproved_scope.status = "draft"  # NOT approved
    est = generate_project_estimate(unapproved_scope)

    with pytest.raises(ValueError, match="Cannot run follow-up diff against unapproved scope"):
        compare_scope_against_baseline(unapproved_scope, est, "transcript_c", [])


def test_scope_diff_real_stored_baseline_and_transcript_c():
    """Real database baseline test: 5 stored baseline requirements + Transcript C facts.

    Asserts exactly:
    - 1 added (Twilio SMS 2FA)
    - 1 removed (Newsletter, req-transcript_a-3)
    - 0 modified
    - 4 unchanged (a-1, a-2, a-4, a-5)
    - +20 days timeline shift
    - summary counts match list lengths
    - hours_delta and cost_delta strictly equal estimate differences
    - strict invariant: buckets sum to baseline total (4 unchanged + 1 removed = 5)
    """
    # 1. Load real 5 stored baseline requirements from committed JSON fixture
    fixture_path = Path(__file__).parent / "fixtures" / "baseline_lawyers_directory.json"
    raw_fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    baseline_reqs = [Requirement.model_validate(item) for item in raw_fixture]

    approved_scope = generate_scope_document(
        project_id="proj_lawyers_directory",
        project_name="Lawyers Directory Portal",
        requirements=baseline_reqs,
        target_date="2026-11-15",
        version=1,
    )
    approved_scope.status = "approved"
    approved_scope.approved_by = "Emily Watson, Managing Director"

    baseline_estimate = generate_project_estimate(approved_scope)

    # 2. Setup Transcript C facts with classification
    transcript_c_candidates = [
        # c-1: Legitimate requirement addition
        Requirement(
            id="req-transcript_c-1",
            transcript_id="transcript_c",
            project_id="proj_lawyers_directory",
            description="Twilio SMS 2FA integration for attorney registration and profile management",
            source_quote="First, our security compliance committee has mandated two-factor authentication. We want to ADD an SMS two-factor verification requirement using Twilio when attorneys register or edit their profile credentials. (Emily Watson at 00:03:10)",
            statement_type="requirement_change",
        ),
        # c-2: Duplicate mention by consultant (confirmation chatter)
        Requirement(
            id="req-transcript_c-2",
            transcript_id="transcript_c",
            project_id="proj_lawyers_directory",
            description="Twilio SMS 2FA integration for attorney registration and profile management",
            source_quote="Got it. That is an ADDED requirement: Twilio SMS 2FA integration for attorney registration and profile management.",
            statement_type="confirmation_or_chatter",
        ),
        # c-3: Client removal intent
        Requirement(
            id="req-transcript_c-3",
            transcript_id="transcript_c",
            project_id="proj_lawyers_directory",
            description="Monthly legal newsletter campaign broadcast",
            source_quote="Second, regarding the mass email campaign integration with Mailchimp that we discussed: our marketing VP confirmed we already pay for HubSpot enterprise. We have decided to REMOVE the mass email marketing integration from your scope entirely, as our internal team will sync contacts to HubSpot on their own. (Emily Watson at 00:06:00)",
            statement_type="requirement_change",
        ),
        # c-4: Date change (timeline_change, not a requirement!)
        Requirement(
            id="req-transcript_c-4",
            transcript_id="transcript_c",
            project_id="proj_lawyers_directory",
            description="Delivery date milestone change",
            source_quote="Can we move the final delivery milestone from November 15 to December 5, 2026?",
            statement_type="timeline_change",
        ),
        # c-5: Chatter turn
        Requirement(
            id="req-transcript_c-5",
            transcript_id="transcript_c",
            project_id="proj_lawyers_directory",
            description="Chatter",
            source_quote="That will be marked as REMOVED from the active scope",
            statement_type="confirmation_or_chatter",
        ),
    ]

    # 3. Execute diff
    rev_scope, rev_est, diff_report = compare_scope_against_baseline(
        baseline_scope=approved_scope,
        baseline_estimate=baseline_estimate,
        new_transcript_id="transcript_c",
        new_requirements=transcript_c_candidates,
        new_target_date="2026-12-05",
    )

    # 4. Strict assertions matching the real database baseline:
    # Exactly 1 added (Twilio SMS 2FA)
    assert len(diff_report.added_requirements) == 1
    assert "Twilio" in diff_report.added_requirements[0]

    # Exactly 1 removed (Newsletter, req-transcript_a-3)
    assert len(diff_report.removed_requirements) == 1
    assert "req-transcript_a-3" in diff_report.removed_requirements[0]
    assert "newsletter" in diff_report.removed_requirements[0].lower()

    # Exactly 0 modified
    assert len(diff_report.modified_requirements) == 0

    # Exactly 4 unchanged baseline requirements (a-1, a-2, a-4, a-5)
    assert len(diff_report.unchanged_requirements) == 4
    unchanged_text = " ".join(diff_report.unchanged_requirements)
    assert "req-transcript_a-1" in unchanged_text
    assert "req-transcript_a-2" in unchanged_text
    assert "req-transcript_a-4" in unchanged_text
    assert "req-transcript_a-5" in unchanged_text

    # STRICT ACCOUNTING INVARIANT ON REAL STORED BASELINE:
    # Every single baseline requirement must land in exactly one bucket, and the buckets must sum to the baseline total
    total_bucketed = (
        len(diff_report.unchanged_requirements)
        + len(diff_report.modified_requirements)
        + len(diff_report.removed_requirements)
        + len(diff_report.conflicts)
        + len(diff_report.not_a_requirement_items)
    )
    assert total_bucketed == len(baseline_reqs) == 5

    # Timeline shifted by +20 days
    assert "+20 days" in diff_report.timeline_delta
    assert "2026-11-15" in diff_report.timeline_delta
    assert "2026-12-05" in diff_report.timeline_delta

    # Summary counts must strictly equal list lengths
    assert f"Added: {len(diff_report.added_requirements)}" in diff_report.summary
    assert f"Removed: {len(diff_report.removed_requirements)}" in diff_report.summary
    assert f"Modified: {len(diff_report.modified_requirements)}" in diff_report.summary
    assert f"Unchanged: {len(diff_report.unchanged_requirements)}" in diff_report.summary

    # hours_delta and cost_delta must strictly equal difference between estimates
    expected_hours_delta = round(rev_est.total_likely_hours - baseline_estimate.total_likely_hours, 1)
    expected_cost_delta = round(rev_est.estimated_cost_likely - baseline_estimate.estimated_cost_likely, 2)

    assert diff_report.hours_delta == expected_hours_delta
    assert diff_report.cost_delta == expected_cost_delta
