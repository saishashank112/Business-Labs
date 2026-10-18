import argparse
import csv
import json
import time
import asyncio
import sys
import os
from pathlib import Path

# Add task1 root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db
from retrieval.rag import answer_query
from app.config import settings


def load_prices() -> dict:
    prices_path = Path(__file__).parent.parent.parent / "config" / "prices.json"
    if prices_path.exists():
        try:
            return json.loads(prices_path.read_text(encoding="utf-8")).get("models", {})
        except Exception:
            pass
    return {}


def estimate_case_cost(model_name: str, input_tokens: int, output_tokens: int, prices: dict) -> float:
    model_pricing = prices.get(model_name, {})
    in_rate = model_pricing.get("input_cost_per_million", 0.30)
    out_rate = model_pricing.get("output_cost_per_million", 2.50)
    return round((input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate, 6)


async def run_task1_evaluations(
    limit: int | None = None,
    max_cost: float | None = None,
    dry_run: bool = False,
    force_cache_off: bool = False,
    models_to_eval: list[str] | None = None,
) -> dict:
    if "--real" in sys.argv or force_cache_off:
        settings.llm_cache_enabled = False
        print("Real evaluation mode: LLM cache FORCED OFF.")
    else:
        print(f"Evaluation mode: LLM cache is {'ENABLED' if settings.llm_cache_enabled else 'OFF'}.")

    prices = load_prices()

    eval_dir = Path(__file__).parent
    cases_path = eval_dir / "cases.json"
    results_dir = eval_dir / "results"
    results_dir.mkdir(exist_ok=True)
    csv_path = results_dir / "eval_results.csv"

    all_cases = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = all_cases[:limit] if limit is not None else all_cases

    from llm.claude_budget import get_claude_budget_summary

    if not models_to_eval:
        models_to_eval = [
            getattr(settings, "claude_model_fast", "") or "claude-haiku-5-5",
            getattr(settings, "claude_model_strong", "") or "claude-sonnet-5-5",
            getattr(settings, "grader_model", "") or "gemini-2.5-flash-lite",
        ]

    # Enforce --max-cost pricing policy for live runs
    if max_cost is not None and not dry_run:
        for m in models_to_eval:
            m_pricing = prices.get(m, {})
            if not m_pricing or m_pricing.get("input_cost_per_million") is None:
                raise RuntimeError(
                    f"Pricing for configured model '{m}' is missing in config/prices.json. "
                    "Cannot enforce --max-cost without pricing rates (will not assume zero cost). Refusing to run."
                )
            if not m_pricing.get("verified"):
                print(f"[Notice] Pricing for '{m}' is unverified in config/prices.json. Proceeding with configured rates (${m_pricing.get('input_cost_per_million')}/${m_pricing.get('output_cost_per_million')} per MTok).")

    # DRY-RUN SAFETY CHECK
    if dry_run:
        print("\n=== [TASK 1: KNOWLEDGE BRAIN — DRY-RUN MODE (ZERO CALLS)] ===")
        total_estimated_calls = len(models_to_eval) * len(cases)
        total_est_cost = 0.0

        model_stats = {}
        for m in models_to_eval:
            model_stats[m] = {"calls": len(cases), "in_tokens": 0, "out_tokens": 0, "cost": 0.0}

        for c in cases:
            est_in = len(c["question"].split()) * 4 + 350
            est_out = 150
            for m in models_to_eval:
                c_cost = estimate_case_cost(m, est_in, est_out, prices)
                model_stats[m]["in_tokens"] += est_in
                model_stats[m]["out_tokens"] += est_out
                model_stats[m]["cost"] += c_cost
                total_est_cost += c_cost

        print(f"Cases Evaluated: {len(cases)} (limit={limit}) | Total Planned Calls: {total_estimated_calls}")
        print("\n| Task | Model | Planned Calls | Est. Input Tokens | Est. Output Tokens | Total Est. Tokens | Est. Cost (USD) |")
        print("|---|---|---:|---:|---:|---:|---:|")
        for m, stats in model_stats.items():
            tot_tok = stats["in_tokens"] + stats["out_tokens"]
            print(f"| Task 1 (Knowledge Brain) | `{m}` | {stats['calls']} | {stats['in_tokens']} | {stats['out_tokens']} | {tot_tok} | ${stats['cost']:.6f} |")

        print(f"\nTotal Estimated Spend across all {len(models_to_eval)} models: ${total_est_cost:.6f} USD")
        if max_cost is not None:
            print(f"Configured Safety Budget (--max-cost): ${max_cost:.4f} USD")

        budget_summary = get_claude_budget_summary()
        print(f"\n[GLOBAL CLAUDE BUDGET STATUS] Running Total: ${budget_summary['running_total_usd']:.4f} / ${budget_summary['max_total_claude_usd']:.2f} USD (Remaining: ${budget_summary['remaining_usd']:.4f} USD | Claude Calls Logged: {budget_summary['calls_count']})")
        print("=== DRY-RUN COMPLETE (Zero real model calls made, zero tokens consumed) ===\n")
        return {"dry_run": True, "planned_calls": total_estimated_calls, "estimated_cost": total_est_cost, "model_stats": model_stats}

    await init_db()
    results = []
    accumulated_cost = 0.0
    budget_exhausted = False

    print(f"Starting Task 1 Evaluations ({len(cases)} cases across {len(models_to_eval)} models, max_cost={max_cost})...")

    for model_name in models_to_eval:
        if budget_exhausted:
            break

        is_claude = "claude" in model_name.lower()
        key_missing = is_claude and not (getattr(settings, "claude_api_key", "") or getattr(settings, "anthropic_api_key", ""))

        print(f"\n--- Model: {model_name} {'[PENDING - NO API KEY]' if key_missing else ''} ---")

        for case in cases:
            cid = case["id"]
            q = case["question"]
            exp_status = case["expected_status"]

            if max_cost is not None and accumulated_cost >= max_cost:
                print(f"⚠️ SAFETY STOP: Accumulated cost (${accumulated_cost:.4f}) reached --max-cost (${max_cost:.4f}). Halting evaluation.")
                budget_exhausted = True
                break

            if key_missing:
                results.append({
                    "task": "task1",
                    "case_id": cid,
                    "model": model_name,
                    "expected": exp_status,
                    "actual": "pending",
                    "quality": "pending",
                    "latency_ms": 0,
                    "cost": 0.0,
                    "passed": "pending",
                    "failure_reason": "pending: no API key configured for model",
                    "cache_hit": False,
                    "prompt_version": "rag_v1",
                    "grader_model": getattr(settings, "grader_model", "gemini-2.5-flash-lite"),
                    "grader_prompt_version": "eval_grader_v1",
                })
                continue

            t0 = time.time()
            try:
                settings.t1_rag_model = model_name
                resp = await answer_query(question=q, mode="hybrid")
                dur_ms = int((time.time() - t0) * 1000)

                status_match = resp.status == exp_status
                escalation_match = (resp.needs_human is True) if case.get("should_escalate") else True
                passed = status_match and escalation_match
                failure_reason = "" if passed else f"Expected status '{exp_status}', got '{resp.status}'"
                cache_hit = (dur_ms < 60) and settings.llm_cache_enabled

                in_tok = len(q.split()) * 4 + 350
                out_tok = len(resp.answer.split()) * 2
                case_cost = 0.0 if cache_hit else estimate_case_cost(model_name, in_tok, out_tok, prices)
                accumulated_cost += case_cost

                results.append({
                    "task": "task1",
                    "case_id": cid,
                    "model": model_name,
                    "expected": exp_status,
                    "actual": resp.status,
                    "quality": "pass" if passed else "fail",
                    "latency_ms": dur_ms,
                    "cost": case_cost,
                    "passed": passed,
                    "failure_reason": failure_reason,
                    "cache_hit": cache_hit,
                    "prompt_version": "rag_v1",
                    "grader_model": getattr(settings, "grader_model", "gemini-2.5-flash-lite"),
                    "grader_prompt_version": "eval_grader_v1",
                })
                print(f"  [{cid}] {'PASS' if passed else 'FAIL'} ({dur_ms}ms) [cost=${case_cost:.6f}, total=${accumulated_cost:.4f}]")
            except Exception as e:
                dur_ms = int((time.time() - t0) * 1000)
                results.append({
                    "task": "task1",
                    "case_id": cid,
                    "model": model_name,
                    "expected": exp_status,
                    "actual": "error",
                    "quality": "error",
                    "latency_ms": dur_ms,
                    "cost": 0.0,
                    "passed": False,
                    "failure_reason": str(e),
                    "cache_hit": False,
                    "prompt_version": "rag_v1",
                    "grader_model": getattr(settings, "grader_model", "gemini-2.5-flash-lite"),
                    "grader_prompt_version": "eval_grader_v1",
                })
                print(f"  [{cid}] ERROR ({e})")

    # Write partial or full CSV
    fieldnames = [
        "task",
        "case_id",
        "model",
        "expected",
        "actual",
        "quality",
        "latency_ms",
        "cost",
        "passed",
        "failure_reason",
        "cache_hit",
        "prompt_version",
        "grader_model",
        "grader_prompt_version",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nTask 1 Eval Results saved to: {csv_path} (Total rows: {len(results)}, Total cost: ${accumulated_cost:.4f})")
    budget_summary = get_claude_budget_summary()
    print(f"[GLOBAL CLAUDE BUDGET STATUS] Running Total: ${budget_summary['running_total_usd']:.4f} / ${budget_summary['max_total_claude_usd']:.2f} USD (Remaining: ${budget_summary['remaining_usd']:.4f} USD | Claude Calls: {budget_summary['calls_count']})\n")
    return {"csv_path": str(csv_path), "total_rows": len(results), "total_cost": accumulated_cost}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Task 1 Eval Runner")
    parser.add_argument("--limit", "-n", type=int, default=None, help="Limit number of eval cases")
    parser.add_argument("--max-cost", type=float, default=None, help="Maximum spend budget in USD")
    parser.add_argument("--dry-run", action="store_true", help="Print planned calls and estimated cost without model calls")
    parser.add_argument("--real", action="store_true", help="Disable LLM cache")
    args = parser.parse_args()

    asyncio.run(run_task1_evaluations(
        limit=args.limit,
        max_cost=args.max_cost,
        dry_run=args.dry_run,
        force_cache_off=args.real,
    ))
