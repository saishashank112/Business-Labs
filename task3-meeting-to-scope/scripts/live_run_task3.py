import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.transcript_analyst import extract_requirements_from_dialogue
from agents.scope_agent import generate_scope_document
from agents.estimation_agent import generate_project_estimate
from scope_diff.comparator import compare_scope_against_baseline

async def run_live_pipeline():
    base_dir = Path(__file__).parent.parent
    trans_a_path = base_dir / "transcripts" / "transcript_a.json"
    trans_c_path = base_dir / "transcripts" / "transcript_c.json"

    data_a = json.loads(trans_a_path.read_text(encoding="utf-8"))
    data_c = json.loads(trans_c_path.read_text(encoding="utf-8"))

    print("=== LIVE RUN: ANALYZE TRANSCRIPT A ===")
    reqs_a = await extract_requirements_from_dialogue(
        transcript_id=data_a["id"],
        project_id=data_a["project_id"],
        dialogue=data_a["dialogue"],
    )

    print(f"Extraction Mode for Transcript A: {reqs_a[0].extraction_mode if reqs_a else 'none'}")
    print(f"Total Extracted Requirements: {len(reqs_a)}")
    for idx, r in enumerate(reqs_a, 1):
        print(f"  {idx}. [{r.id}] ({r.statement_type}) - {r.description}")
        print(f"      Quote: {r.source_quote}")

    # Build and Approve baseline scope
    baseline_scope = generate_scope_document(
        project_id=data_a["project_id"],
        project_name=data_a["project_name"],
        requirements=reqs_a,
        target_date=data_a["target_delivery_date"],
        version=1,
    )
    baseline_scope.status = "approved"
    baseline_scope.approved_by = "Emily Watson"
    baseline_estimate = generate_project_estimate(baseline_scope)

    print(f"\nBaseline Scope Approved: {baseline_scope.id} (Version {baseline_scope.version})")
    print(f"Baseline Estimate: {baseline_estimate.total_likely_hours}h | ${baseline_estimate.estimated_cost_likely} {baseline_estimate.currency}")

    print("\n=== LIVE RUN: ANALYZE AND COMPARE TRANSCRIPT C ===")
    reqs_c = await extract_requirements_from_dialogue(
        transcript_id=data_c["id"],
        project_id=data_c["project_id"],
        dialogue=data_c["dialogue"],
    )

    print(f"Extraction Mode for Transcript C: {reqs_c[0].extraction_mode if reqs_c else 'none'}")
    print(f"Total Statements Extracted from Transcript C: {len(reqs_c)}")
    for idx, r in enumerate(reqs_c, 1):
        print(f"  {idx}. [{r.id}] ({r.statement_type}) - {r.description}")
        print(f"      Quote: {r.source_quote}")

    rev_scope, rev_est, diff_report = compare_scope_against_baseline(
        baseline_scope=baseline_scope,
        baseline_estimate=baseline_estimate,
        new_transcript_id=data_c["id"],
        new_requirements=reqs_c,
        new_target_date=data_c["target_delivery_date"],
        extraction_mode=reqs_c[0].extraction_mode if reqs_c else "llm",
    )

    print("\n=== LIVE SCOPE DIFF REPORT ===")
    print(f"Diff Report ID: {diff_report.id}")
    print(f"Extraction Mode: {diff_report.extraction_mode}")
    print(f"Added Requirements ({len(diff_report.added_requirements)}):")
    for item in diff_report.added_requirements:
        print(f"  + {item}")
    print(f"Removed Requirements ({len(diff_report.removed_requirements)}):")
    for item in diff_report.removed_requirements:
        print(f"  - {item}")
    print(f"Modified Requirements ({len(diff_report.modified_requirements)}):")
    for item in diff_report.modified_requirements:
        print(f"  * {item}")
    print(f"Unchanged Requirements ({len(diff_report.unchanged_requirements)}):")
    for item in diff_report.unchanged_requirements:
        print(f"  = {item}")
    print(f"Non-Requirement / Chatter Items ({len(diff_report.not_a_requirement_items)}):")
    for item in diff_report.not_a_requirement_items:
        print(f"  ~ {item}")
    print(f"Timeline Delta: {diff_report.timeline_delta}")
    print(f"Hours Delta: {diff_report.hours_delta:+.1f} hours")
    print(f"Cost Delta: ${diff_report.cost_delta:+,.2f} USD")
    print(f"\nRevised Estimate: {rev_est.total_likely_hours}h | ${rev_est.estimated_cost_likely} {rev_est.currency}")
    print(f"Baseline Estimate: {baseline_estimate.total_likely_hours}h | ${baseline_estimate.estimated_cost_likely} {baseline_estimate.currency}")
    print(f"Arithmetic Verification: {rev_est.total_likely_hours} - {baseline_estimate.total_likely_hours} = {rev_est.total_likely_hours - baseline_estimate.total_likely_hours:.1f} (Report delta: {diff_report.hours_delta})")

if __name__ == "__main__":
    asyncio.run(run_live_pipeline())
