"""Response cache for LLM calls.

Avoids duplicate API calls, conserving quota and latency during repeated testing,
demos, and development runs. Can be toggled on/off via settings.llm_cache_enabled.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Optional, Any
import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)


def compute_cache_key(
    model: str,
    step: str,
    system_prompt: Optional[str],
    prompt: str,
    schema_name: Optional[str] = None,
) -> str:
    """Compute a deterministic SHA-256 cache key from model parameters and prompts."""
    raw = f"{model}::{step}::{system_prompt or ''}::{prompt}::{schema_name or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def init_cache_db() -> None:
    """Initialize the llm_cache table if it doesn't already exist."""
    async with aiosqlite.connect(settings.t1_db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                step TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        await db.commit()


async def get_cached_response(cache_key: str) -> Optional[dict[str, Any]]:
    """Retrieve cached response data if caching is enabled."""
    if not getattr(settings, "llm_cache_enabled", True):
        return None

    try:
        async with aiosqlite.connect(settings.t1_db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT response_json FROM llm_cache WHERE cache_key = ?",
                (cache_key,),
            )
            row = await cursor.fetchone()
            if row:
                return json.loads(row["response_json"])
    except Exception as e:
        logger.warning("Failed to read from LLM cache: %s", e)
    return None


async def set_cached_response(
    cache_key: str,
    model: str,
    step: str,
    response_data: dict[str, Any],
) -> None:
    """Save an LLM response into the cache table."""
    if not getattr(settings, "llm_cache_enabled", True):
        return

    try:
        await init_cache_db()
        async with aiosqlite.connect(settings.t1_db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO llm_cache (cache_key, model, step, response_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cache_key, model, step, json.dumps(response_data), time.time()),
            )
            await db.commit()
    except Exception as e:
        logger.warning("Failed to write to LLM cache: %s", e)
