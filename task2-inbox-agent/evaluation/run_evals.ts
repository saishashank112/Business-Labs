import fs from "node:fs";
import path from "node:path";
import { classifyEmail } from "../src/lib/classifier";
import { checkGuardrails } from "../src/lib/guardrails";
import { EmailMessage } from "../src/lib/schemas";

async function runTask2Evaluations() {
  const emailsPath = path.resolve(process.cwd(), "data", "emails.json");
  const emails: EmailMessage[] = JSON.parse(fs.readFileSync(emailsPath, "utf-8"));

  const resultsDir = path.resolve(process.cwd(), "evaluation", "results");
  fs.mkdirSync(resultsDir, { recursive: true });
  const csvPath = path.join(resultsDir, "eval_results.csv");

  console.log(`Starting Task 2 Inbox Agent Evals (${emails.length} emails, including holdout set)...`);

  const results: any[] = [];
  const latencies: number[] = [];
  let categoryMatches = 0;
  let guardrailMatches = 0;

  for (const email of emails) {
    const t0 = Date.now();
    try {
      const classification = await classifyEmail(email);
      const durMs = Date.now() - t0;
      latencies.push(durMs);

      // Check classification match
      const catMatch = !email.expected_category || classification.category === email.expected_category;
      if (catMatch) categoryMatches++;

      // Check risk / guardrail match
      const mockDraft: any = {
        category: classification.category,
        summary: "Summary",
        suggested_reply:
          classification.category === "refund"
            ? "Your refund request has been received and routed to accounts."
            : "Instructions from documentation.",
        sources: [],
        risk_level: classification.risk_level,
        needs_human_approval: classification.risk_level === "high",
        next_action: "Review",
      };

      const guardrail = checkGuardrails(mockDraft, classification);
      const isHighRisk = email.expected_risk === "high" || email.expected_category === "refund" || email.expected_category === "complaint";
      const expectedAutoSend = !isHighRisk;
      const autoSendMatch = guardrail.autoSendAllowed === expectedAutoSend;
      if (autoSendMatch) guardrailMatches++;

      const passed = catMatch && autoSendMatch;

      results.push({
        id: email.id,
        category: classification.category,
        expected_category: email.expected_category,
        risk: classification.risk_level,
        expected_risk: email.expected_risk,
        is_holdout: email.is_holdout,
        category_match: catMatch,
        auto_send_allowed: guardrail.autoSendAllowed,
        passed,
        latency_ms: durMs,
      });

      console.log(`  [${email.id}] ${passed ? "PASS" : "FAIL"} | ${classification.category} (${durMs}ms)`);
    } catch (err: any) {
      const durMs = Date.now() - t0;
      results.push({
        id: email.id,
        category: "error",
        expected_category: email.expected_category,
        risk: "error",
        expected_risk: email.expected_risk,
        is_holdout: email.is_holdout,
        category_match: false,
        auto_send_allowed: false,
        passed: false,
        latency_ms: durMs,
      });
    }
  }

  // Write CSV
  const header = "id,category,expected_category,risk,expected_risk,is_holdout,category_match,auto_send_allowed,passed,latency_ms\n";
  const rows = results
    .map(
      (r) =>
        `${r.id},${r.category},${r.expected_category},${r.risk},${r.expected_risk},${r.is_holdout},${r.category_match},${r.auto_send_allowed},${r.passed},${r.latency_ms}`,
    )
    .join("\n");

  fs.writeFileSync(csvPath, header + rows, "utf-8");

  latencies.sort((a, b) => a - b);
  const p50 = latencies[Math.floor(latencies.length / 2)] || 0;
  const p95 = latencies[Math.floor(latencies.length * 0.95)] || 0;
  const accuracy = ((categoryMatches / emails.length) * 100).toFixed(1);

  console.log("\n--- Task 2 Eval Summary ---");
  console.log(`Category Accuracy: ${accuracy}% (${categoryMatches}/${emails.length})`);
  console.log(`Guardrail Compliance: ${((guardrailMatches / emails.length) * 100).toFixed(1)}%`);
  console.log(`Latency: p50=${p50}ms | p95=${p95}ms`);
  console.log(`CSV saved to: ${csvPath}\n`);
}

runTask2Evaluations();
