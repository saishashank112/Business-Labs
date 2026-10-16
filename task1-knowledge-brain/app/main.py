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
    from app.config import settings
    if not settings.t1_api_key or settings.t1_api_key.strip() == "change-me-in-production":
        raise RuntimeError(
            "CRITICAL SECURITY CONFIG ERROR: T1_API_KEY must be set in .env to a non-default secret and cannot be 'change-me-in-production'."
        )

    if getattr(settings, "profile", "dev") == "final":
        claude_fast = getattr(settings, "claude_model_fast", "")
        claude_strong = getattr(settings, "claude_model_strong", "")
        if not claude_fast or not claude_strong:
            raise RuntimeError(
                "Final profile requires CLAUDE_MODEL_FAST and CLAUDE_MODEL_STRONG to be configured with verified IDs in .env. "
                "One or both are currently empty placeholders. Refusing to run final profile."
            )
        anthropic_key = getattr(settings, "anthropic_api_key", "") or getattr(settings, "claude_api_key", "")
        if not anthropic_key:
            raise RuntimeError("Final profile requires ANTHROPIC_API_KEY in .env. Refusing to run.")
        from llm.claude_provider import verify_claude_models
        check_res = await verify_claude_models(anthropic_key, [claude_fast, claude_strong])
        for m in [claude_fast, claude_strong]:
            if not check_res.get("models", {}).get(m):
                raise RuntimeError(
                    f"Configured Claude model ID '{m}' was not returned by Anthropic models list endpoint. "
                    "Refusing to run final profile with unverified model ID."
                )

    await init_db()       # create tables if missing
    try:
        from llm.gemini_provider import check_model_availability
        await check_model_availability()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Startup model availability check failed: %s", e)
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
