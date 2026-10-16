"""FastAPI entry point — the Knowledge Brain API.

Run with:  uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
"""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app.database import init_db
from app.routes import health, ingestion, query, escalation


# ── Lifespan (startup / shutdown) ───────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once on startup, yields, then runs on shutdown."""
    await init_db()       # create tables if missing
    try:
        from ingestion.scheduler import start_scheduler, shutdown_scheduler
        start_scheduler()
    except Exception:
        pass
    yield                 # app runs here
    try:
        from ingestion.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass


# ── App instance ────────────────────────────────────────────

app = FastAPI(
    title="Knowledge Brain API",
    description="AI-powered help-center knowledge base with RAG",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Middleware: attach a unique request ID to every request ──

@app.middleware("http")
async def add_request_id(request: Request, call_next) -> Response:
    """Give every request a unique ID for tracing and logging."""
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# ── Mount route groups ──────────────────────────────────────

app.include_router(health.router)
app.include_router(ingestion.router, tags=["ingestion"])
app.include_router(query.router, tags=["query"])
app.include_router(escalation.router)
