"""Global Budget Guard for Claude LLM calls across the project."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm.interface import LLMError

logger = logging.getLogger(__name__)


def find_workspace_root() -> Path:
    cur = Path(__file__).resolve().parent
    for _ in range(5):
        if (cur / "config" / "claude_spend_ledger.json").exists() or (cur / "config" / "prices.json").exists():
            return cur
        cur = cur.parent
    return Path(os.getcwd())


def get_ledger_path() -> Path:
    root = find_workspace_root()
    return root / "config" / "claude_spend_ledger.json"


def get_prices_path() -> Path:
    root = find_workspace_root()
    return root / "config" / "prices.json"


def get_model_rates(model_name: str) -> tuple[float, float]:
    """Return (input_rate_per_million, output_rate_per_million) from config/prices.json."""
    prices_path = get_prices_path()
    if prices_path.exists():
        try:
            data = json.loads(prices_path.read_text(encoding="utf-8"))
            m_pricing = data.get("models", {}).get(model_name, {})
            if m_pricing:
                in_rate = m_pricing.get("input_cost_per_million")
                out_rate = m_pricing.get("output_cost_per_million")
                if in_rate is not None and out_rate is not None:
                    return float(in_rate), float(out_rate)
        except Exception as e:
            logger.warning("Could not read rates from %s: %s", prices_path, e)

    if "sonnet" in model_name.lower():
        return 2.00, 10.00
    if "haiku" in model_name.lower():
        return 0.10, 0.50
    return 0.50, 2.50


def load_ledger() -> dict[str, Any]:
    ledger_path = get_ledger_path()
    if ledger_path.exists():
        try:
            return json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to parse ledger %s: %s", ledger_path, e)

    max_budget = float(os.getenv("MAX_TOTAL_CLAUDE_USD", "3.50"))
    return {
        "max_total_claude_usd": max_budget,
        "running_total_usd": 0.0,
        "calls_count": 0,
        "calls": [],
    }


from filelock import FileLock


def get_lock_path() -> Path:
    return get_ledger_path().with_suffix(".lock")


def save_ledger(data: dict[str, Any]) -> None:
    ledger_path = get_ledger_path()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = ledger_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_path.replace(ledger_path)


def check_claude_budget() -> float:
    """Check running total against MAX_TOTAL_CLAUDE_USD before initiating a Claude call.
    Raises LLMError(BUDGET_EXHAUSTED) if limit reached.
    """
    lock = FileLock(str(get_lock_path()), timeout=10)
    with lock:
        ledger = load_ledger()
        max_budget = float(os.getenv("MAX_TOTAL_CLAUDE_USD", str(ledger.get("max_total_claude_usd", 3.50))))
        running_total = float(ledger.get("running_total_usd", 0.0))

        if running_total >= max_budget:
            msg = (
                f"Global Claude budget guard ceiling reached: running total ${running_total:.4f} USD >= "
                f"MAX_TOTAL_CLAUDE_USD (${max_budget:.2f} USD). Refusing new Claude call."
            )
            logger.error(msg)
            raise LLMError(code="BUDGET_EXHAUSTED", message=msg)

        return running_total


def record_claude_call(
    task: str,
    step: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    request_id: str | None = None,
) -> float:
    """Calculate call cost, record call in the ledger, and update running total.
    Returns cost of the call in USD.
    """
    in_rate, out_rate = get_model_rates(model)
    cost = round((input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate, 6)

    # In automated test suite, do not write test mock calls into production spend ledger
    if os.getenv("PYTEST_CURRENT_TEST"):
        return cost

    lock = FileLock(str(get_lock_path()), timeout=10)
    with lock:
        ledger = load_ledger()
        max_budget = float(os.getenv("MAX_TOTAL_CLAUDE_USD", str(ledger.get("max_total_claude_usd", 3.50))))
        old_total = float(ledger.get("running_total_usd", 0.0))
        new_total = round(old_total + cost, 6)

        call_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": task,
            "step": step,
            "model": model,
            "request_id": request_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "running_total_usd": new_total,
        }

        calls = ledger.get("calls", [])
        calls.append(call_record)
        ledger["calls"] = calls
        ledger["calls_count"] = len(calls)
        ledger["running_total_usd"] = new_total
        ledger["max_total_claude_usd"] = max_budget

        save_ledger(ledger)
        rem = max(0.0, max_budget - new_total)
    print(
        f"[BUDGET GUARD] Claude Call Logged: {model} ({input_tokens} in, {output_tokens} out) -> "
        f"${cost:.6f} USD | Running Total: ${new_total:.4f} / ${max_budget:.2f} USD (Remaining: ${rem:.4f} USD)"
    )
    return cost


def get_claude_budget_summary() -> dict[str, Any]:
    ledger = load_ledger()
    max_budget = float(os.getenv("MAX_TOTAL_CLAUDE_USD", str(ledger.get("max_total_claude_usd", 3.50))))
    running_total = float(ledger.get("running_total_usd", 0.0))
    return {
        "running_total_usd": running_total,
        "max_total_claude_usd": max_budget,
        "remaining_usd": max(0.0, max_budget - running_total),
        "calls_count": ledger.get("calls_count", 0),
    }
