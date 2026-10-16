"""POST /ingestion/run  and  GET /ingestion/status

Starts a background crawl job and reports its progress.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies import verify_api_key
from app.models import IngestionRequest, IngestionStarted, IngestionStatus

router = APIRouter()

# Simple in-memory state for the current job.
# Fine for a single-server, single-user capstone project.
_current_job: dict | None = None


async def _run_ingestion(job_id: str, max_pages: int | None) -> None:
    """Background task: fetch sitemap → crawl → parse → store."""
    global _current_job
    try:
        from ingestion.pipeline import run_ingestion_pipeline

        report = await run_ingestion_pipeline(max_pages=max_pages)

        _current_job = {
            "job_id": job_id,
            "status": "completed",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "report": report,
        }
    except Exception as exc:
        _current_job = {
            "job_id": job_id,
            "status": "failed",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "report": None,
            "error": str(exc),
        }


@router.post("/ingestion/run", response_model=IngestionStarted)
async def start_ingestion(
    body: IngestionRequest,
    background_tasks: BackgroundTasks,
    _key: str = Depends(verify_api_key),
) -> IngestionStarted:
    """Kick off a crawl-and-parse job in the background."""
    global _current_job

    job_id = str(uuid.uuid4())
    _current_job = {"job_id": job_id, "status": "running"}
    background_tasks.add_task(_run_ingestion, job_id, body.max_pages)
    return IngestionStarted(job_id=job_id)


@router.get("/ingestion/status", response_model=IngestionStatus)
async def get_ingestion_status(
    _key: str = Depends(verify_api_key),
) -> IngestionStatus:
    """Return the current ingestion job status and last report."""
    if _current_job is None:
        return IngestionStatus(status="idle")
    return IngestionStatus(
        status=_current_job["status"],
        last_run=_current_job.get("last_run"),
        report=_current_job.get("report"),
    )
