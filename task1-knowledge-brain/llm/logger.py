"""LLM call logging — logs token counts, latency, and estimated cost to SQLite.

Every LLM interaction writes a row to llm_log table for cost and latency auditability.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db

logger = logging.getLogger(__name__)

# Price estimates per 1,000,000 tokens (USD)
RATES = {
    "gemini": {
        "input": 0.10,
        "output": 0.40,
    },
    "claude-sonnet": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-haiku": {
        "input": 0.80,
        "output": 4.00,
    },
    "default": {
        "input": 0.50,
        "output": 1.50,
    },
}


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate approximate USD cost for an LLM call."""
    prov_lower = provider.lower()
    mod_lower = model.lower()

    if "gemini" in prov_lower or "gemini" in mod_lower:
        rate = RATES["gemini"]
    elif "haiku" in mod_lower:
        rate = RATES["claude-haiku"]
    elif "claude" in prov_lower or "sonnet" in mod_lower:
        rate = RATES["claude-sonnet"]
    else:
        rate = RATES["default"]

    cost = (input_tokens / 1_000_000 * rate["input"]) + (output_tokens / 1_000_000 * rate["output"])
    return round(cost, 6)


async def log_llm_call(
    request_id: Optional[str],
    step: str,
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    cost_usd: Optional[float] = None,
) -> None:
    """Record an LLM call into SQLite llm_log table."""
    if cost_usd is None:
        cost_usd = estimate_cost(provider, model, input_tokens, output_tokens)

    now = datetime.now(timezone.utc).isoformat()
    try:
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO llm_log
                   (request_id, step, model, provider, input_tokens, output_tokens, latency_ms, cost_usd, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request_id,
                    step,
                    model,
                    provider,
                    input_tokens,
                    output_tokens,
                    latency_ms,
                    cost_usd,
                    now,
                ),
            )
            await db.commit()
        finally:
            await db.close()
    except Exception as e:
        logger.error("Failed to write to llm_log: %s", e)
