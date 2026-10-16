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
    return {
        "status": "ok",
        "service": "task3-meeting-to-scope",
        "uptime_seconds": round(time.time() - _start_time, 2),
    }


app.include_router(transcripts.router)
app.include_router(analysis.router)
app.include_router(approval.router)
