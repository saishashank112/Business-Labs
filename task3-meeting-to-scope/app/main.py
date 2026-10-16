from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response

from app.database import init_db
from app.routes import transcripts, analysis, approval

_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import settings
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

    await init_db()
    yield


app = FastAPI(
    title="Meeting to Scope API — AI Tech Consultant",
    description="Multi-agent transcript analysis, product feasibility, scoping, and diff engine",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next) -> Response:
    req_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    request.state.request_id = req_id
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    return response


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    from app.config import settings

    claude_info = None
    anthropic_key = getattr(settings, "anthropic_api_key", "") or getattr(settings, "claude_api_key", "")
    if anthropic_key:
        from llm.claude_provider import verify_claude_models
        models_to_check = [
            getattr(settings, "claude_model_fast", ""),
            getattr(settings, "claude_model_strong", ""),
        ]
        models_to_check = [m for m in models_to_check if m]
        if models_to_check:
            claude_info = await verify_claude_models(anthropic_key, models_to_check)

    return {
        "status": "ok",
        "service": "task3-meeting-to-scope",
        "uptime_seconds": round(time.time() - _start_time, 2),
        "claude_status": claude_info or "unconfigured",
    }


app.include_router(transcripts.router)
app.include_router(analysis.router)
app.include_router(approval.router)
