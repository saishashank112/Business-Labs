import { getDb } from "../db";

export function logLlmCall(
  requestId: string | undefined,
  step: string,
  model: string,
  provider: string,
  inputTokens: number,
  outputTokens: number,
  latencyMs: number,
  costUsd?: number,
): void {
  const calculatedCost =
    costUsd !== undefined
      ? costUsd
      : (inputTokens / 1_000_000) * 0.1 + (outputTokens / 1_000_000) * 0.4;

  const now = new Date().toISOString();
  try {
    const db = getDb();
    db.prepare(`
      INSERT INTO llm_log (request_id, step, model, provider, input_tokens, output_tokens, latency_ms, cost_usd, timestamp)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      requestId || null,
      step,
      model,
      provider,
      inputTokens,
      outputTokens,
      latencyMs,
      calculatedCost,
      now,
    );
  } catch (err) {
    console.error("Failed to log LLM call:", err);
  }
}
