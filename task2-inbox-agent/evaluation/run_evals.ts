import fs from "node:fs";
import path from "node:path";
import { classifyEmail } from "../src/lib/classifier";
import { checkGuardrails } from "../src/lib/guardrails";
import { EmailMessage } from "../src/lib/schemas";

function loadPrices(): Record<string, any> {
  const pricesPath = path.resolve(process.cwd(), "..", "config", "prices.json");
  if (fs.existsSync(pricesPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(pricesPath, "utf-8"));
      return data.models || {};
    } catch {
      // fallback
    }
  }
  return {};
}

function estimateCaseCost(modelName: string, inTokens: number, outTokens: number, prices: Record<string, any>): number {
  const modelPricing = prices[modelName] || {};
  const inRate = modelPricing.input_cost_per_million || 0.30;
  const outRate = modelPricing.output_cost_per_million || 2.50;
  return Number(((inTokens / 1_000_000) * inRate + (outTokens / 1_000_000) * outRate).toFixed(6));
}

function parseCliArgs() {
  const args = process.argv.slice(2);
  let limit: number | null = null;
  let maxCost: number | null = null;
  let dryRun = false;
  let real = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--limit" || args[i] === "-n") {
      limit = parseInt(args[++i], 10);
    } else if (args[i] === "--max-cost") {
      maxCost = parseFloat(args[++i]);
    } else if (args[i] === "--dry-run") {
      dryRun = true;
    } else if (args[i] === "--real") {
      real = true;
    }
  }

  return { limit, maxCost, dryRun, real };
}

async function runTask2Evaluations() {
  const { limit, maxCost, dryRun, real } = parseCliArgs();
  const prices = loadPrices();

  const emailsPath = path.resolve(process.cwd(), "data", "emails.json");
  const allEmails: EmailMessage[] = JSON.parse(fs.readFileSync(emailsPath, "utf-8"));
  const emails = limit ? allEmails.slice(0, limit) : allEmails;

  const resultsDir = path.resolve(process.cwd(), "evaluation", "results");
  fs.mkdirSync(resultsDir, { recursive: true });
  const csvPath = path.join(resultsDir, "eval_results.csv");

  if (real) {
    process.env.LLM_CACHE_ENABLED = "false";
    console.log("Real evaluation mode: LLM cache FORCED OFF.");
  } else {
    console.log(`Evaluation mode: LLM cache is ${process.env.LLM_CACHE_ENABLED !== "false" ? "ENABLED" : "OFF"}.`);
  }

  const modelsToEval = [
    process.env.T2_CLASSIFY_MODEL || "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "claude-haiku-placeholder",
  ];

  // DRY-RUN SAFETY CHECK
  if (dryRun) {
    console.log("\n=== [TASK 2 DRY-RUN MODE — NO CALLS WILL BE MADE] ===");
    const totalCalls = modelsToEval.length * emails.length;
    let totalEstCost = 0;
    console.log(`Target Models: ${JSON.stringify(modelsToEval)}`);
    console.log(`Total Emails: ${emails.length} (limit=${limit})`);
    console.log(`Total Planned Calls: ${totalCalls}`);
    console.log("\nPlanned Cases:");
    emails.forEach((email, idx) => {
      const inTok = (email.subject.length + email.body.length) / 3;
      const outTok = 60;
      const caseCost = estimateCaseCost(modelsToEval[0], inTok, outTok, prices) * modelsToEval.length;
      totalEstCost += caseCost;
      console.log(`  ${idx + 1}. [${email.id}] '${email.subject.slice(0, 45)}...' -> Expected: ${email.expected_category || "any"}`);
    });
    if (maxCost !== null) {
      for (const m of modelsToEval) {
        const mPricing = prices[m] || {};
        if (!mPricing.verified || mPricing.input_cost_per_million === null || mPricing.input_cost_per_million === undefined) {
          throw new Error(
            `Pricing for configured model '${m}' is unverified or missing in config/prices.json. Cannot enforce --max-cost without verified pricing (will not assume zero cost). Refusing to run.`
          );
        }
      }
    }

    console.log(`\nEstimated Spend Across All Models: $${totalEstCost.toFixed(6)} USD`);
    if (maxCost !== null) {
      console.log(`Configured Safety Budget (--max-cost): $${maxCost.toFixed(4)} USD`);
    }
    console.log("=== DRY-RUN COMPLETE (Zero spend incurred) ===\n");
    return;
  }

  // Enforce --max-cost verified pricing policy for live runs as well
  if (maxCost !== null) {
    for (const m of modelsToEval) {
      const mPricing = prices[m] || {};
      if (!mPricing.verified || mPricing.input_cost_per_million === null || mPricing.input_cost_per_million === undefined) {
        throw new Error(
          `Pricing for configured model '${m}' is unverified or missing in config/prices.json. Cannot enforce --max-cost without verified pricing (will not assume zero cost). Refusing to run.`
        );
      }
    }
  }

  console.log(`Starting Task 2 Inbox Agent Evals (${emails.length} emails across ${modelsToEval.length} models, maxCost=${maxCost})...`);

  const results: any[] = [];
  let accumulatedCost = 0;
  let budgetExhausted = false;

  for (const modelName of modelsToEval) {
    if (budgetExhausted) break;

    const isClaude = modelName.toLowerCase().includes("claude");
    const keyMissing = isClaude && !(process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY);

    console.log(`\n--- Model: ${modelName} ${keyMissing ? "[PENDING - NO API KEY]" : ""} ---`);

    for (const email of emails) {
      if (maxCost !== null && accumulatedCost >= maxCost) {
        console.log(`⚠️ SAFETY STOP: Accumulated spend ($${accumulatedCost.toFixed(4)}) reached --max-cost ($${maxCost.toFixed(4)}). Halting evaluation.`);
        budgetExhausted = true;
        break;
      }

      if (keyMissing) {
        results.push({
          task: "task2",
          case_id: email.id,
          model: modelName,
          expected: email.expected_category || "any",
          actual: "pending",
          quality: "pending",
          latency_ms: 0,
          cost: 0.0,
          passed: "pending",
          failure_reason: "pending: no API key configured for model",
          cache_hit: false,
          prompt_version: "classify_v1",
          grader_model: process.env.GRADER_MODEL || "gemini-2.5-flash-lite",
          grader_prompt_version: "eval_grader_v1",
        });
        continue;
      }

      const t0 = Date.now();
      try {
        process.env.T2_CLASSIFY_MODEL = modelName;
        const classification = await classifyEmail(email);
        const durMs = Date.now() - t0;

        const catMatch = !email.expected_category || classification.category === email.expected_category;
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
        const passed = catMatch && autoSendMatch;
        const cacheHit = durMs < 60 && process.env.LLM_CACHE_ENABLED !== "false";

        const inTok = (email.subject.length + email.body.length) / 3;
        const outTok = 60;
        const caseCost = cacheHit ? 0.0 : estimateCaseCost(modelName, inTok, outTok, prices);
        accumulatedCost += caseCost;

        results.push({
          task: "task2",
          case_id: email.id,
          model: modelName,
          expected: email.expected_category || "any",
          actual: classification.category,
          quality: passed ? "pass" : "fail",
          latency_ms: durMs,
          cost: caseCost,
          passed,
          failure_reason: passed ? "" : `Expected category ${email.expected_category}, got ${classification.category}`,
          cache_hit: cacheHit,
          prompt_version: "classify_v1",
          grader_model: process.env.GRADER_MODEL || "gemini-2.5-flash-lite",
          grader_prompt_version: "eval_grader_v1",
        });

        console.log(`  [${email.id}] ${passed ? "PASS" : "FAIL"} | ${classification.category} (${durMs}ms) [cost=$${caseCost.toFixed(6)}, total=$${accumulatedCost.toFixed(4)}]`);
      } catch (err: any) {
        const durMs = Date.now() - t0;
        results.push({
          task: "task2",
          case_id: email.id,
          model: modelName,
          expected: email.expected_category || "any",
          actual: "error",
          quality: "error",
          latency_ms: durMs,
          cost: 0.0,
          passed: false,
          failure_reason: err.message || String(err),
          cache_hit: false,
          prompt_version: "classify_v1",
          grader_model: process.env.GRADER_MODEL || "gemini-2.5-flash-lite",
          grader_prompt_version: "eval_grader_v1",
        });
      }
    }
  }

  // Write CSV matching unified schema
  const header = "task,case_id,model,expected,actual,quality,latency_ms,cost,passed,failure_reason,cache_hit,prompt_version,grader_model,grader_prompt_version\n";
  const rows = results
    .map(
      (r) =>
        `${r.task},${r.case_id},${r.model},${r.expected},${r.actual},${r.quality},${r.latency_ms},${r.cost},${r.passed},"${(r.failure_reason || "").replace(/"/g, '""')}",${r.cache_hit},${r.prompt_version},${r.grader_model},${r.grader_prompt_version}`,
    )
    .join("\n");

  fs.writeFileSync(csvPath, header + rows, "utf-8");
  console.log(`\nTask 2 Eval Results saved to: ${csvPath} (Total rows: ${results.length}, Total cost: $${accumulatedCost.toFixed(4)})`);
}

if (require.main === module) {
  runTask2Evaluations().catch(console.error);
}

export { runTask2Evaluations };
