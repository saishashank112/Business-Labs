from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db

logger = logging.getLogger(__name__)


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    if "claude" in provider.lower() or "sonnet" in model.lower():
        cost = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)
    else:
        cost = (input_tokens / 1_000_000 * 0.10) + (output_tokens / 1_000_000 * 0.40)
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
        logger.error("Failed to write to llm_log in task 3: %s", e)
