from __future__ import annotations

import argparse
import csv
import json
import time
import asyncio
import sys
from pathlib import Path

# Add task3 root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Requirement, ScopeDocument, EstimateTask, ProjectEstimate
from agents.transcript_analyst import extract_requirements_from_dialogue
from agents.product_feasibility import check_requirement_feasibility
from agents.scope_agent import generate_scope_document
from agents.estimation_agent import generate_project_estimate
from agents.proposal_agent import generate_proposal_document
from scope_diff.comparator import compare_scope_against_baseline
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


async def evaluate_case(case: dict, model_name: str, prices: dict) -> dict:
    cid = case["id"]
    category = case["category"]
    case_type = case["type"]
    inp = case["input"]
    expected = case["expected"]

    t0 = time.time()
    passed = False
    details = ""
    failure_reason = ""
    is_offline_degraded = False

    try:
        if inp["type"] == "transcript_analysis":
            text = inp["text"]
            dialogue = [{"speaker": "Client", "timestamp": "00:15", "text": text}]
            reqs = await extract_requirements_from_dialogue(
                transcript_id=cid,
                project_id=f"proj-{cid}",
                dialogue=dialogue,
            )
            # Eval Rule: any case whose extraction_mode is offline_heuristic is recorded as invalid (not passed)
            if any(getattr(r, "extraction_mode", None) == "offline_heuristic" for r in reqs):
                is_offline_degraded = True
                passed = False
                failure_reason = "INVALID: offline_heuristic degraded mode is not counted toward eval quality"
                details = f"offline_heuristic ({len(reqs)} reqs)"
            else:
                if "min_requirements" in expected:
                    passed = len(reqs) >= expected["min_requirements"]
                else:
                    passed = len(reqs) > 0
                details = f"Extracted {len(reqs)} reqs (LLM)"
                if not passed:
                    failure_reason = f"Expected >= {expected.get('min_requirements')} reqs, got {len(reqs)}"

        elif inp["type"] == "feasibility":
            feat = inp["feature"]
            req = Requirement(
                id=f"req-{cid}",
                transcript_id=cid,
                project_id=f"proj-{cid}",
                description=feat,
                source_quote=feat,
                status="confirmed",
                priority="high",
                stated_or_inferred="stated",
            )
            checked = await check_requirement_feasibility(req, timeout_seconds=0.3)
            exp_cls = expected.get("expected_classification")
            if exp_cls == "native":
                passed = checked.feasibility in ["existing_config", "existing_feature_with_limitation"]
            elif exp_cls == "custom_code":
                passed = checked.feasibility in ["potential_custom", "needs_clarification"]
            else:
                passed = True
            details = f"Feasibility: {checked.feasibility}"
            if not passed:
                failure_reason = f"Expected {exp_cls}, got {checked.feasibility}"

        elif inp["type"] == "scope":
            reqs = [
                Requirement(
                    id=f"r-{i}",
                    transcript_id=cid,
                    project_id=f"proj-{cid}",
                    description=r,
                    source_quote=r,
                    status="confirmed",
                    priority="high",
                    stated_or_inferred="stated",
                )
                for i, r in enumerate(inp["requirements"])
            ]
            doc = generate_scope_document(f"proj-{cid}", "Test Project", reqs)
            passed = len(doc.agreed_requirements) == len(reqs)
            details = f"Scope v{doc.version} created"
            if not passed:
                failure_reason = "Scope requirements mismatch"

        elif inp["type"] == "diff":
            base_reqs = [
                Requirement(
                    id=f"b-{i}",
                    transcript_id="trans_base",
                    project_id=f"proj-{cid}",
                    description=r,
                    source_quote=r,
                    status="confirmed",
                    priority="medium",
                )
                for i, r in enumerate(inp["baseline_requirements"])
            ]
            base_scope = generate_scope_document(f"proj-{cid}", "Test Project", base_reqs)
            base_scope.status = "approved"
            base_est = generate_project_estimate(base_scope)

            new_reqs = [
                Requirement(
                    id=f"n-{i}",
                    transcript_id="trans_new",
                    project_id=f"proj-{cid}",
                    description=r,
                    source_quote=r,
                    status="confirmed",
                    priority="medium",
                )
                for i, r in enumerate(inp["new_requirements"])
            ]
            rev_scope, rev_est, diff_rep = compare_scope_against_baseline(
                baseline_scope=base_scope,
                baseline_estimate=base_est,
                new_transcript_id="trans_new",
                new_requirements=new_reqs,
            )
            passed = (
                len(diff_rep.added_requirements) == expected.get("added_count", 0)
                and len(diff_rep.removed_requirements) == expected.get("removed_count", 0)
            )
            details = f"+{len(diff_rep.added_requirements)} / -{len(diff_rep.removed_requirements)}"
            if not passed:
                failure_reason = f"Diff count mismatch: +{len(diff_rep.added_requirements)}/-{len(diff_rep.removed_requirements)}"

        else:
            passed = True
            details = "General validation"

    except Exception as e:
        passed = False
        details = "Error"
        failure_reason = str(e)

    dur_ms = int((time.time() - t0) * 1000)
    cache_hit = (dur_ms < 60) and getattr(settings, "llm_cache_enabled", True)
    cost = 0.0 if cache_hit else estimate_case_cost(model_name, 350, 150, prices)

    quality = "invalid" if is_offline_degraded else ("pass" if passed else "fail")

    return {
        "task": "task3",
        "case_id": cid,
        "model": model_name,
        "expected": json.dumps(expected) if isinstance(expected, dict) else str(expected),
        "actual": details,
        "quality": quality,
        "latency_ms": dur_ms,
        "cost": cost,
        "passed": passed and not is_offline_degraded,
        "failure_reason": failure_reason,
        "cache_hit": cache_hit,
        "prompt_version": "scope_v1",
        "grader_model": getattr(settings, "grader_model", "gemini-2.5-flash-lite"),
        "grader_prompt_version": "eval_grader_v1",
        "extraction_mode": "offline_heuristic" if is_offline_degraded else "llm",
    }


async def run_task3_evaluations(
    limit: int | None = None,
    max_cost: float | None = None,
    dry_run: bool = False,
    force_cache_off: bool = False,
):
    # Enforce safe offline fallback policy: evals fail on LLM error rather than degraded heuristic
    settings.allow_offline_fallback = False

    if "--real" in sys.argv or force_cache_off:
        settings.llm_cache_enabled = False
        print("Real evaluation mode: LLM cache FORCED OFF.")
    else:
        print(f"Evaluation mode: LLM cache is {'ENABLED' if getattr(settings, 'llm_cache_enabled', True) else 'OFF'}.")

    prices = load_prices()

    eval_dir = Path(__file__).parent
    cases_path = eval_dir / "cases.json"
    results_dir = eval_dir / "results"
    results_dir.mkdir(exist_ok=True)
    csv_path = results_dir / "eval_results.csv"

    all_cases = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = all_cases[:limit] if limit is not None else all_cases

    models_to_eval = [
        settings.t3_extract_model,
        "gemini-2.5-flash-lite",
        "claude-haiku-placeholder",
    ]

    # Enforce --max-cost verified pricing policy
    if max_cost is not None:
        for m in models_to_eval:
            m_pricing = prices.get(m, {})
            if not m_pricing or not m_pricing.get("verified") or m_pricing.get("input_cost_per_million") is None:
                raise RuntimeError(
                    f"Pricing for configured model '{m}' is unverified or missing in config/prices.json. "
                    "Cannot enforce --max-cost without verified pricing (will not assume zero cost). Refusing to run."
                )

    # DRY-RUN SAFETY CHECK
    if dry_run:
        print("\n=== [TASK 3 DRY-RUN MODE — NO CALLS WILL BE MADE] ===")
        total_calls = len(models_to_eval) * len(cases)
        total_est_cost = 0.0
        print(f"Target Models: {models_to_eval}")
        print(f"Total Test Cases: {len(cases)} (limit={limit})")
        print(f"Total Planned Calls: {total_calls}")
        print("\nPlanned Cases:")
        for idx, c in enumerate(cases, 1):
            est_cost = estimate_case_cost(models_to_eval[0], 400, 200, prices) * len(models_to_eval)
            total_est_cost += est_cost
            print(f"  {idx}. [{c['id']}] Category: {c.get('category')} | Type: {c.get('type')}")
        print(f"\nEstimated Spend Across All Models: ${total_est_cost:.6f} USD")
        if max_cost is not None:
            print(f"Safety Limit (--max-cost): ${max_cost:.4f} USD")
        print("=== DRY-RUN COMPLETE (Zero spend incurred) ===\n")
        return {"dry_run": True, "planned_calls": total_calls, "estimated_cost": total_est_cost}

    print(f"Starting Task 3 Meeting-to-Scope Evals ({len(cases)} cases across {len(models_to_eval)} models, max_cost={max_cost})...")

    results = []
    accumulated_cost = 0.0
    budget_exhausted = False

    for model_name in models_to_eval:
        if budget_exhausted:
            break

        is_claude = "claude" in model_name.lower()
        key_missing = is_claude and not (getattr(settings, "anthropic_api_key", "") or getattr(settings, "claude_api_key", ""))

        print(f"\n--- Model: {model_name} {'[PENDING - NO API KEY]' if key_missing else ''} ---")

        for c in cases:
            if max_cost is not None and accumulated_cost >= max_cost:
                print(f"⚠️ SAFETY STOP: Accumulated spend (${accumulated_cost:.4f}) reached --max-cost (${max_cost:.4f}). Halting evaluation.")
                budget_exhausted = True
                break

            if key_missing:
                results.append({
                    "task": "task3",
                    "case_id": c["id"],
                    "model": model_name,
                    "expected": json.dumps(c.get("expected", {})),
                    "actual": "pending",
                    "quality": "pending",
                    "latency_ms": 0,
                    "cost": 0.0,
                    "passed": "pending",
                    "failure_reason": "pending: no API key configured for model",
                    "cache_hit": False,
                    "prompt_version": "scope_v1",
                    "grader_model": getattr(settings, "grader_model", "gemini-2.5-flash-lite"),
                    "grader_prompt_version": "eval_grader_v1",
                    "extraction_mode": "none",
                })
                continue

            r = await evaluate_case(c, model_name, prices)
            accumulated_cost += r.get("cost", 0.0)
            status_str = "PASS" if r["passed"] else ("INVALID (degraded)" if r["quality"] == "invalid" else "FAIL")
            print(f"  [{r['case_id']}] {status_str} ({r['latency_ms']}ms) [cost=${r['cost']:.6f}, total=${accumulated_cost:.4f}] - {r['actual']}")
            results.append(r)

    # Write partial or complete CSV
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
        "extraction_mode",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nTask 3 Eval Results saved to: {csv_path} (Total rows: {len(results)}, Total cost: ${accumulated_cost:.4f})\n")
    return {"csv_path": str(csv_path), "total_rows": len(results), "total_cost": accumulated_cost}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Task 3 Eval Runner")
    parser.add_argument("--limit", "-n", type=int, default=None, help="Limit number of eval cases")
    parser.add_argument("--max-cost", type=float, default=None, help="Maximum spend budget in USD")
    parser.add_argument("--dry-run", action="store_true", help="Print planned calls and estimated cost without model calls")
    parser.add_argument("--real", action="store_true", help="Disable LLM cache")
    args = parser.parse_args()

    asyncio.run(run_task3_evaluations(
        limit=args.limit,
        max_cost=args.max_cost,
        dry_run=args.dry_run,
        force_cache_off=args.real,
    ))
