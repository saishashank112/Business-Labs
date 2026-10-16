"""GET /health — system liveness and model availability check."""

import time

from fastapi import APIRouter

from app.models import HealthResponse
from app.config import settings

router = APIRouter(tags=["health"])

# Record when the module was first imported (≈ server start)
_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service status, DB connection, and configured LLM model availability."""
    from llm.gemini_provider import get_model_health

    health_info = await get_model_health()
    model_status = health_info.get("status", "available")
    overall_status = "ok" if model_status in ("available", "fallback_active") else "degraded"

    claude_info = None
    if getattr(settings, "claude_api_key", ""):
        from llm.claude_provider import verify_claude_models
        models_to_check = [
            getattr(settings, "claude_model_fast", "claude-3-5-haiku-20241022"),
            getattr(settings, "claude_model_strong", "claude-3-5-sonnet-20241022"),
        ]
        claude_info = await verify_claude_models(settings.claude_api_key, models_to_check)

    return HealthResponse(
        status=overall_status,
        db="connected",
        model=settings.t1_rag_model,
        model_status=model_status,
        fallback_model=getattr(settings, "t1_fallback_model", None),
        claude_status=claude_info,
        uptime_seconds=round(time.time() - _start_time, 1),
    )

