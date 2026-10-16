"""Escalation management routes — human-in-the-loop for unanswerable questions.

When evidence is missing or contradictory, an escalation is created.
When an expert provides the verified answer, it is stored in expert_knowledge
and immediately feeds future retrieval.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.database import get_db
from app.dependencies import verify_api_key

router = APIRouter(prefix="/escalations", tags=["escalations"])


# ── Schemas ─────────────────────────────────────────────────

class EscalationCreate(BaseModel):
    question: str = Field(..., min_length=1)
    evidence: Optional[str] = None
    reason: Optional[str] = None


class EscalationResolve(BaseModel):
    answer: str = Field(..., min_length=1)
    reviewer: str = Field(..., min_length=1)
    expires_at: Optional[str] = None


class EscalationItem(BaseModel):
    id: str
    question: str
    evidence: Optional[str] = None
    reason: Optional[str] = None
    status: str
    created_at: str
    resolved_at: Optional[str] = None
    resolver: Optional[str] = None


# ── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=list[EscalationItem])
async def list_escalations(
    status: Optional[str] = None,
    _: str = Depends(verify_api_key),
) -> list[EscalationItem]:
    """List escalations, optionally filtered by status ('open' or 'resolved')."""
    db = await get_db()
    try:
        if status:
            cursor = await db.execute(
                "SELECT * FROM escalations WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM escalations ORDER BY created_at DESC"
            )
        rows = await cursor.fetchall()
        return [
            EscalationItem(
                id=r["id"],
                question=r["question"],
                evidence=r["evidence"],
                reason=r["reason"],
                status=r["status"],
                created_at=r["created_at"],
                resolved_at=r["resolved_at"],
                resolver=r["resolver"],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("", status_code=201)
async def create_escalation_endpoint(
    body: EscalationCreate,
    req: Request,
    _: str = Depends(verify_api_key),
) -> dict:
    """Manually or programmatically create an escalation."""
    request_id = getattr(req.state, "request_id", None)
    esc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO escalations
               (id, question, evidence, reason, status, created_at, request_id)
               VALUES (?, ?, ?, ?, 'open', ?, ?)""",
            (esc_id, body.question, body.evidence, body.reason, now, request_id),
        )
        await db.commit()
    finally:
        await db.close()

    return {"id": esc_id, "status": "open"}


@router.post("/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: str,
    body: EscalationResolve,
    _: str = Depends(verify_api_key),
) -> dict:
    """Resolve an open escalation with human-verified answer and ingest into expert_knowledge."""
    db = await get_db()
    try:
        # Check escalation exists
        cursor = await db.execute("SELECT question, status FROM escalations WHERE id = ?", (escalation_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Escalation not found")

        now = datetime.now(timezone.utc).isoformat()
        question = row["question"]

        # Update escalation
        await db.execute(
            """UPDATE escalations
               SET status = 'resolved', resolved_at = ?, resolver = ?
               WHERE id = ?""",
            (now, body.reviewer, escalation_id),
        )

        # Insert into expert_knowledge
        knowledge_id = f"ek-{uuid.uuid4().hex[:8]}"
        await db.execute(
            """INSERT INTO expert_knowledge
               (id, escalation_id, question, answer, reviewed, reviewer, version, expires_at, created_at)
               VALUES (?, ?, ?, ?, 1, ?, 1, ?, ?)""",
            (knowledge_id, escalation_id, question, body.answer, body.reviewer, body.expires_at, now),
        )
        await db.commit()

        # Also index this expert knowledge chunk into FTS5 immediately
        try:
            from app.models import Chunk
            from ingestion.keyword_index import index_chunks_fts

            expert_chunk = Chunk(
                chunk_id=knowledge_id,
                article_id=knowledge_id,
                url="#expert-knowledge",
                title=f"Expert: {question}",
                heading="Verified Answer",
                content=f"# Expert Knowledge by {body.reviewer}\n\nQ: {question}\n\nA: {body.answer}",
                chunk_index=0,
            )
            await index_chunks_fts([expert_chunk])
        except Exception:
            pass

        return {
            "id": escalation_id,
            "status": "resolved",
            "knowledge_id": knowledge_id,
        }
    finally:
        await db.close()
