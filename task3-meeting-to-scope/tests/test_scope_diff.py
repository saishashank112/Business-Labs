import pytest
from app.models import Requirement, ScopeDocument, ProjectEstimate
from agents.scope_agent import generate_scope_document
from agents.estimation_agent import generate_project_estimate
from scope_diff.comparator import compare_scope_against_baseline


def test_scope_diff_rejects_unapproved_baseline():
    req1 = Requirement(id="r1", transcript_id="tA", project_id="p1", description="CSV import", source_quote="quote")
    unapproved_scope = generate_scope_document("p1", "Test Project", [req1])
    unapproved_scope.status = "draft"  # NOT approved
    est = generate_project_estimate(unapproved_scope)

    with pytest.raises(ValueError, match="Cannot run follow-up diff against unapproved scope"):
        compare_scope_against_baseline(unapproved_scope, est, "transcript_c", [])


def test_scope_diff_with_approved_baseline():
    # Baseline requirements from Transcript A
    req_csv = Requirement(id="req-1", transcript_id="tA", project_id="p1", description="Import categories via CSV", source_quote="CSV quote")
    req_fwd = Requirement(id="req-2", transcript_id="tA", project_id="p1", description="Email forwarders setup", source_quote="Fwd quote")
    req_mass = Requirement(id="req-3", transcript_id="tA", project_id="p1", description="Mass email campaign setup", source_quote="Mass email quote")

    approved_scope = generate_scope_document("p1", "Test Project", [req_csv, req_fwd, req_mass], target_date="2026-11-15", version=1)
    approved_scope.status = "approved"
    approved_scope.approved_by = "Emily Watson"

    baseline_est = generate_project_estimate(approved_scope)

    # Transcript C additions & removals
    req_sms = Requirement(id="req-c-1", transcript_id="tC", project_id="p1", description="Twilio SMS 2FA integration", source_quote="SMS quote")
    req_remove_mass = Requirement(id="req-c-2", transcript_id="tC", project_id="p1", description="Remove mass email campaign", source_quote="Remove quote")

    rev_scope, rev_est, diff_report = compare_scope_against_baseline(
        baseline_scope=approved_scope,
        baseline_estimate=baseline_est,
        new_transcript_id="transcript_c",
        new_requirements=[req_sms, req_remove_mass],
        new_target_date="2026-12-05",
    )

    assert rev_scope.version == 2
    assert rev_scope.target_delivery_date == "2026-12-05"
    assert len(diff_report.added_requirements) >= 1
    assert any("Twilio" in a or "SMS" in a for a in diff_report.added_requirements)
    assert len(diff_report.removed_requirements) >= 1
    assert any("Mass email" in rm for rm in diff_report.removed_requirements)
    assert "Dec 5" in diff_report.timeline_delta or "2026-12-05" in diff_report.timeline_delta
    assert diff_report.hours_delta != 0
