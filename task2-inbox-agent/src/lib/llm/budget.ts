import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export interface ClaudeSpendRecord {
  timestamp: string;
  task: string;
  step: string;
  model: string;
  request_id?: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  running_total_usd: number;
}

export interface ClaudeSpendLedger {
  max_total_claude_usd: number;
  running_total_usd: number;
  calls_count: number;
  calls: ClaudeSpendRecord[];
}

function findWorkspaceRoot(): string {
  let cur = process.cwd();
  for (let i = 0; i < 5; i++) {
    if (
      fs.existsSync(path.join(cur, "config", "claude_spend_ledger.json")) ||
      fs.existsSync(path.join(cur, "config", "prices.json"))
    ) {
      return cur;
    }
    cur = path.dirname(cur);
  }
  return path.resolve(process.cwd(), "..");
}

export function getLedgerPath(): string {
  const root = findWorkspaceRoot();
  return path.join(root, "config", "claude_spend_ledger.json");
}

export function getPricesPath(): string {
  const root = findWorkspaceRoot();
  return path.join(root, "config", "prices.json");
}

export function getModelRates(modelName: string): { inRate: number; outRate: number } {
  const pricesPath = getPricesPath();
  if (fs.existsSync(pricesPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(pricesPath, "utf-8"));
      const mPricing = data.models?.[modelName];
      if (mPricing && mPricing.input_cost_per_million !== undefined && mPricing.output_cost_per_million !== undefined) {
        return {
          inRate: Number(mPricing.input_cost_per_million),
          outRate: Number(mPricing.output_cost_per_million),
        };
      }
    } catch {
      // fallback
    }
  }

  if (modelName.toLowerCase().includes("sonnet")) {
    return { inRate: 2.0, outRate: 10.0 };
  }
  if (modelName.toLowerCase().includes("haiku")) {
    return { inRate: 0.1, outRate: 0.5 };
  }
  return { inRate: 0.5, outRate: 2.5 };
}

export function loadLedger(): ClaudeSpendLedger {
  const ledgerPath = getLedgerPath();
  if (fs.existsSync(ledgerPath)) {
    try {
      return JSON.parse(fs.readFileSync(ledgerPath, "utf-8"));
    } catch {
      // fallback
    }
  }

  const maxBudget = parseFloat(process.env.MAX_TOTAL_CLAUDE_USD || "3.50");
  return {
    max_total_claude_usd: maxBudget,
    running_total_usd: 0.0,
    calls_count: 0,
    calls: [],
  };
}

function withFileLock<T>(action: () => T): T {
  const lockPath = `${getLedgerPath()}.lock`;
  const startTime = Date.now();
  let fd: number | null = null;
  while (fd === null) {
    try {
      fd = fs.openSync(lockPath, "wx");
    } catch (e: any) {
      if (Date.now() - startTime > 8000) {
        try {
          const stats = fs.statSync(lockPath);
          if (Date.now() - stats.mtimeMs > 10000) {
            fs.unlinkSync(lockPath);
          }
        } catch {}
      }
      const waitTill = Date.now() + 30;
      while (Date.now() < waitTill) {}
      if (Date.now() - startTime > 10000) {
        throw new Error("Timeout acquiring Claude spend ledger file lock");
      }
    }
  }

  try {
    return action();
  } finally {
    if (fd !== null) {
      try {
        fs.closeSync(fd);
      } catch {}
      try {
        fs.unlinkSync(lockPath);
      } catch {}
    }
  }
}

export function saveLedger(data: ClaudeSpendLedger): void {
  const ledgerPath = getLedgerPath();
  fs.mkdirSync(path.dirname(ledgerPath), { recursive: true });
  const tempPath = `${ledgerPath}.tmp`;
  fs.writeFileSync(tempPath, JSON.stringify(data, null, 2), "utf-8");
  fs.renameSync(tempPath, ledgerPath);
}

export function checkClaudeBudget(): number {
  return withFileLock(() => {
    const ledger = loadLedger();
    const maxBudget = parseFloat(process.env.MAX_TOTAL_CLAUDE_USD || String(ledger.max_total_claude_usd || 3.50));
    const runningTotal = Number(ledger.running_total_usd || 0.0);

    if (runningTotal >= maxBudget) {
      const msg = `Global Claude budget guard ceiling reached: running total $${runningTotal.toFixed(4)} USD >= MAX_TOTAL_CLAUDE_USD ($${maxBudget.toFixed(2)} USD). Refusing new Claude call.`;
      const err: any = new Error(msg);
      err.code = "BUDGET_EXHAUSTED";
      throw err;
    }

    return runningTotal;
  });
}

export function recordClaudeCall(
  task: string,
  step: string,
  model: string,
  inputTokens: number,
  outputTokens: number,
  requestId?: string,
): number {
  const { inRate, outRate } = getModelRates(model);
  const cost = Number(((inputTokens / 1_000_000) * inRate + (outputTokens / 1_000_000) * outRate).toFixed(6));

  if (process.env.VITEST || process.env.NODE_ENV === "test") {
    return cost;
  }

  return withFileLock(() => {
    const ledger = loadLedger();
    const maxBudget = parseFloat(process.env.MAX_TOTAL_CLAUDE_USD || String(ledger.max_total_claude_usd || 3.50));
    const oldTotal = Number(ledger.running_total_usd || 0.0);
    const newTotal = Number((oldTotal + cost).toFixed(6));

    const callRecord: ClaudeSpendRecord = {
      timestamp: new Date().toISOString(),
      task,
      step,
      model,
      request_id: requestId,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      cost_usd: cost,
      running_total_usd: newTotal,
    };

    ledger.calls.push(callRecord);
    ledger.calls_count = ledger.calls.length;
    ledger.running_total_usd = newTotal;
    ledger.max_total_claude_usd = maxBudget;

    saveLedger(ledger);
    const rem = Math.max(0, maxBudget - newTotal);
    console.log(
      `[BUDGET GUARD] Claude Call Logged: ${model} (${inputTokens} in, ${outputTokens} out) -> $${cost.toFixed(6)} USD | Running Total: $${newTotal.toFixed(4)} / $${maxBudget.toFixed(2)} USD (Remaining: $${rem.toFixed(4)} USD)`
    );
    return cost;
  });
}

export function getClaudeBudgetSummary(): {
  running_total_usd: number;
  max_total_claude_usd: number;
  remaining_usd: number;
  calls_count: number;
} {
  const ledger = loadLedger();
  const maxBudget = parseFloat(process.env.MAX_TOTAL_CLAUDE_USD || String(ledger.max_total_claude_usd || 3.50));
  const runningTotal = Number(ledger.running_total_usd || 0.0);
  return {
    running_total_usd: runningTotal,
    max_total_claude_usd: maxBudget,
    remaining_usd: Math.max(0, maxBudget - runningTotal),
    calls_count: ledger.calls_count || 0,
  };
}
