import csv
import json
import time
import asyncio
import sys
from pathlib import Path

# Add task1 root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db
from retrieval.rag import answer_query


async def run_task1_evaluations() -> dict:
    await init_db()

    eval_dir = Path(__file__).parent
    cases_path = eval_dir / "cases.json"
    results_dir = eval_dir / "results"
    results_dir.mkdir(exist_ok=True)
    csv_path = results_dir / "eval_results.csv"

    cases = json.loads(cases_path.read_text(encoding="utf-8"))

    results = []
    latencies = []
    passed_count = 0

    print(f"Starting Task 1 Evaluations ({len(cases)} test cases)...")

    for case in cases:
        cid = case["id"]
        q = case["question"]
        exp_status = case["expected_status"]

        t0 = time.time()
        try:
            resp = await answer_query(question=q, mode="hybrid")
            dur_ms = int((time.time() - t0) * 1000)
            latencies.append(dur_ms)

            # Verification rules
            status_match = resp.status == exp_status
            escalation_match = (resp.needs_human is True) if case.get("should_escalate") else True

            passed = status_match and escalation_match
            if passed:
                passed_count += 1
                failure_reason = ""
            else:
                failure_reason = f"Expected status '{exp_status}', got '{resp.status}'"

            results.append({
                "case_id": cid,
                "question": q,
                "expected_status": exp_status,
                "actual_status": resp.status,
                "passed": passed,
                "latency_ms": dur_ms,
                "sources_count": len(resp.sources),
                "needs_human": resp.needs_human,
                "failure_reason": failure_reason,
            })
            print(f"  [{cid}] {'PASS' if passed else 'FAIL'} ({dur_ms}ms)")
        except Exception as e:
            dur_ms = int((time.time() - t0) * 1000)
            results.append({
                "case_id": cid,
                "question": q,
                "expected_status": exp_status,
                "actual_status": "error",
                "passed": False,
                "latency_ms": dur_ms,
                "sources_count": 0,
                "needs_human": True,
                "failure_reason": str(e),
            })
            print(f"  [{cid}] ERROR ({e})")

    # Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["case_id", "question", "expected_status", "actual_status", "passed", "latency_ms", "sources_count", "needs_human", "failure_reason"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95_idx = int(len(latencies) * 0.95)
    p95 = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0
    pass_rate = (passed_count / len(cases)) * 100 if cases else 0

    summary = {
        "total_cases": len(cases),
        "passed": passed_count,
        "failed": len(cases) - passed_count,
        "pass_rate_pct": round(pass_rate, 1),
        "median_latency_ms": p50,
        "p95_latency_ms": p95,
        "csv_path": str(csv_path),
    }

    print("\n--- Task 1 Eval Summary ---")
    print(f"Pass Rate: {summary['pass_rate_pct']}% ({passed_count}/{len(cases)})")
    print(f"Latency: p50={p50}ms | p95={p95}ms")
    print(f"CSV saved to: {csv_path}\n")

    return summary


if __name__ == "__main__":
    asyncio.run(run_task1_evaluations())
