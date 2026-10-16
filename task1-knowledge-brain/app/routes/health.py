"""GET /health — simple liveness check."""

import time

from fastapi import APIRouter

from app.models import HealthResponse

router = APIRouter(tags=["health"])

# Record when the module was first imported (≈ server start)
_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service status and uptime in seconds."""
    return HealthResponse(
        status="ok",
        db="connected",
        uptime_seconds=round(time.time() - _start_time, 1),
    )
