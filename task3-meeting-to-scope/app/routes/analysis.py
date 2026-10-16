from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from app.database import get_db, init_db
from app.models import Requirement, ScopeDocument, ProjectEstimate, ProposalDocument
from agents.transcript_analyst import extract_requirements_from_dialogue
from agents.product_feasibility import check_requirement_feasibility
from agents.scope_agent import generate_scope_document
from agents.estimation_agent import generate_project_estimate
from agents.proposal_agent import generate_proposal_document

router = APIRouter(prefix="/api/transcripts", tags=["analysis"])


@router.post("/{transcript_id}/analyze")
async def analyze_transcript(transcript_id: str) -> dict:
    await init_db()

    # 1. Load transcript data (from standard JSON or user text file)
    tdir = Path(__file__).parent.parent.parent / "transcripts"
    udir = Path(__file__).parent.parent.parent / "transcripts_user"
    fpath = tdir / f"{transcript_id}.json"
    ufpath = udir / f"{transcript_id}.txt"

    if fpath.exists():
        data = json.loads(fpath.read_text(encoding="utf-8"))
        project_id = data.get("project_id", "proj_default")
        project_name = data.get("project_name", "Consulting Project")
        target_date = data.get("target_delivery_date", "2026-11-15")
        dialogue = data.get("dialogue", [])
    elif ufpath.exists():
        from agents.transcript_analyst import parse_transcript_text
        dialogue = parse_transcript_text(ufpath.read_text(encoding="utf-8"))
        clean_name = transcript_id.replace("_", " ").title()
        project_id = f"proj_{transcript_id}"
        project_name = clean_name
        target_date = "2026-11-15"
    else:
        raise HTTPException(status_code=404, detail="Transcript not found")

    # 2. Extract requirements (Transcript Analyst)
    raw_reqs = await extract_requirements_from_dialogue(transcript_id, project_id, dialogue)

    # 3. Check feasibility against Task 1 Knowledge Brain (Product Feasibility)
    verified_reqs: list[Requirement] = []
    for r in raw_reqs:
        v_req = await check_requirement_feasibility(r)
        verified_reqs.append(v_req)

    # Check existing versions to keep old ones as history
    db = await get_db()
    cursor_ver = await db.execute("SELECT MAX(version) FROM scope_versions WHERE project_id = ?", (project_id,))
    ver_row = await cursor_ver.fetchone()
    next_ver = (ver_row[0] + 1) if (ver_row and ver_row[0] is not None) else 1

    # 4. Generate Scope of Work (Scope Agent)
    scope = generate_scope_document(
        project_id=project_id,
        project_name=project_name,
        requirements=verified_reqs,
        target_date=target_date,
        version=next_ver,
    )

    # 5. Generate Estimates (Estimation Agent)
    estimate = generate_project_estimate(scope)

    # 6. Generate Proposal (Proposal Agent)
    proposal = generate_proposal_document(scope, estimate)

    # 7. Persist into SQLite
    db = await get_db()
    try:
        # Save project
        await db.execute(
            "INSERT OR REPLACE INTO projects (id, name, created_at) VALUES (?, ?, datetime('now'))",
            (project_id, project_name),
        )

        # Save scope
        await db.execute(
            """INSERT OR REPLACE INTO scope_versions
               (id, project_id, version, content, status, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (scope.id, project_id, scope.version, scope.model_dump_json(), scope.status),
        )

        # Save estimate
        await db.execute(
            """INSERT OR REPLACE INTO estimates
               (id, scope_version_id, project_id, tasks, hourly_rate, currency, total_likely_hours, estimated_cost_likely, version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                estimate.id,
                scope.id,
                project_id,
                json.dumps([t.model_dump() for t in estimate.tasks]),
                estimate.hourly_rate,
                estimate.currency,
                estimate.total_likely_hours,
                estimate.estimated_cost_likely,
                estimate.version,
            ),
        )

        # Save proposal
        await db.execute(
            """INSERT OR REPLACE INTO proposals
               (id, project_id, scope_version_id, estimate_id, content, version, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (proposal.id, project_id, scope.id, estimate.id, proposal.model_dump_json(), 1, proposal.status),
        )
        await db.commit()
    finally:
        await db.close()

    extraction_mode = verified_reqs[0].extraction_mode if verified_reqs else "llm"

    return {
        "transcript_id": transcript_id,
        "project_id": project_id,
        "extraction_mode": extraction_mode,
        "requirements": [r.model_dump() for r in verified_reqs],
        "scope": scope.model_dump(),
        "estimate": estimate.model_dump(),
        "proposal": proposal.model_dump(),
    }
