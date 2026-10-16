from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db, init_db
from app.models import ScopeDocument, ProjectEstimate, ScopeDiffReport
from scope_diff.comparator import compare_scope_against_baseline
from agents.transcript_analyst import extract_requirements_from_dialogue
from agents.product_feasibility import check_requirement_feasibility

router = APIRouter(prefix="/api/projects", tags=["approval"])


class ApprovalRequest(BaseModel):
    scope_version_id: str
    reviewer: str = "Authorized Reviewer"


class CompareRequest(BaseModel):
    baseline_scope_id: str
    follow_up_transcript_id: str = "transcript_c"


@router.post("/{project_id}/approve")
async def approve_scope(project_id: str, body: ApprovalRequest) -> dict:
    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT content, status FROM scope_versions WHERE id = ?",
            (body.scope_version_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scope version not found")

        if row["status"] == "degraded_offline" or json.loads(row["content"]).get("extraction_mode") == "offline_heuristic":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Scope '{body.scope_version_id}' is marked as 'degraded_offline'. "
                    "Degraded scopes cannot be approved as baselines for evals or demos. "
                    "When a model is available, rebuild the baseline with the LLM."
                ),
            )

        scope_dict = json.loads(row["content"])
        now = datetime.now(timezone.utc).isoformat()

        scope_dict["status"] = "approved"
        scope_dict["approved_by"] = body.reviewer
        scope_dict["approved_at"] = now

        # Update scope_versions table
        await db.execute(
            """UPDATE scope_versions
               SET status = 'approved', approved_by = ?, approved_at = ?, content = ?
               WHERE id = ?""",
            (body.reviewer, now, json.dumps(scope_dict), body.scope_version_id),
        )

        # Also update corresponding proposal if exists
        await db.execute(
            """UPDATE proposals
               SET status = 'approved', approved_by = ?, approved_at = ?
               WHERE scope_version_id = ?""",
            (body.reviewer, now, body.scope_version_id),
        )
        await db.commit()

        return {
            "success": True,
            "message": f"Scope {body.scope_version_id} has been formally APPROVED.",
            "approved_by": body.reviewer,
            "approved_at": now,
        }
    finally:
        await db.close()


@router.post("/{project_id}/compare")
async def compare_follow_up(project_id: str, body: CompareRequest) -> dict:
    await init_db()
    db = await get_db()
    try:
        # 1. Fetch baseline scope
        cursor = await db.execute(
            "SELECT content, status FROM scope_versions WHERE id = ?",
            (body.baseline_scope_id,),
        )
        scope_row = await cursor.fetchone()
        if not scope_row:
            raise HTTPException(status_code=404, detail="Baseline scope not found")

        # 2. Strict PRD Gate: Baseline MUST be approved and not degraded!
        if scope_row["status"] == "degraded_offline":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Baseline scope '{body.baseline_scope_id}' is marked as 'degraded_offline'. "
                    "Degraded scopes cannot be used for evals or demo diffing. Rebuild with LLM."
                ),
            )
        if scope_row["status"] != "approved":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Baseline scope '{body.baseline_scope_id}' is in '{scope_row['status']}' state. "
                    "Follow-up comparisons require an APPROVED baseline before diffing."
                ),
            )

        baseline_scope = ScopeDocument.model_validate_json(scope_row["content"])

        # Fetch baseline estimate
        cursor_est = await db.execute(
            "SELECT tasks, hourly_rate, currency, total_likely_hours, estimated_cost_likely FROM estimates WHERE scope_version_id = ?",
            (body.baseline_scope_id,),
        )
        est_row = await cursor_est.fetchone()
        if est_row:
            baseline_estimate = ProjectEstimate(
                id=f"est-{baseline_scope.id}",
                scope_version_id=baseline_scope.id,
                project_id=project_id,
                total_likely_hours=est_row["total_likely_hours"],
                estimated_cost_likely=est_row["estimated_cost_likely"],
            )
        else:
            from agents.estimation_agent import generate_project_estimate
            baseline_estimate = generate_project_estimate(baseline_scope)

        # 3. Load follow-up transcript (Transcript C)
        tdir = Path(__file__).parent.parent.parent / "transcripts"
        fpath = tdir / f"{body.follow_up_transcript_id}.json"
        if not fpath.exists():
            raise HTTPException(status_code=404, detail="Follow-up transcript not found")

        follow_up_data = json.loads(fpath.read_text(encoding="utf-8"))
        follow_up_dialogue = follow_up_data.get("dialogue", [])
        new_target_date = follow_up_data.get("target_delivery_date", "2026-12-05")

        # 4. Extract new requirements
        raw_new_reqs = await extract_requirements_from_dialogue(
            body.follow_up_transcript_id,
            project_id,
            follow_up_dialogue,
        )

        verified_new_reqs = []
        for r in raw_new_reqs:
            vr = await check_requirement_feasibility(r)
            verified_new_reqs.append(vr)

        # 5. Run Scope Diff against approved baseline
        revised_scope, revised_estimate, diff_report = compare_scope_against_baseline(
            baseline_scope=baseline_scope,
            baseline_estimate=baseline_estimate,
            new_transcript_id=body.follow_up_transcript_id,
            new_requirements=verified_new_reqs,
            new_target_date=new_target_date,
        )

        # 6. Save revised scope and change report to DB
        await db.execute(
            """INSERT OR REPLACE INTO scope_versions
               (id, project_id, version, content, status, created_at)
               VALUES (?, ?, ?, ?, 'draft', datetime('now'))""",
            (revised_scope.id, project_id, revised_scope.version, revised_scope.model_dump_json()),
        )

        await db.execute(
            """INSERT OR REPLACE INTO change_reports
               (id, project_id, baseline_scope_id, new_transcript_id, added, modified, removed, out_of_scope, conflicts, summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                diff_report.id,
                project_id,
                diff_report.baseline_scope_id,
                diff_report.new_transcript_id,
                json.dumps(diff_report.added_requirements),
                json.dumps(diff_report.modified_requirements),
                json.dumps(diff_report.removed_requirements),
                json.dumps(diff_report.out_of_scope_items),
                json.dumps(diff_report.conflicts),
                diff_report.summary,
            ),
        )
        await db.commit()

        return {
            "success": True,
            "extraction_mode": diff_report.extraction_mode,
            "diff_report": diff_report.model_dump(),
            "revised_scope": revised_scope.model_dump(),
            "revised_estimate": revised_estimate.model_dump(),
        }
    finally:
        await db.close()
