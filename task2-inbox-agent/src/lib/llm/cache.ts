import crypto from "node:crypto";
import { getDb } from "../db";
import { LLMResponse } from "./interface";

export function computeCacheKey(
  model: string,
  step: string,
  systemPrompt?: string,
  prompt: string = "",
): string {
  const raw = `${model}::${step}::${systemPrompt || ""}::${prompt}`;
  return crypto.createHash("sha256").update(raw).digest("hex");
}

export function isCacheEnabled(): boolean {
  return process.env.LLM_CACHE_ENABLED !== "false";
}

export function getCachedResponse(cacheKey: string): LLMResponse | null {
  if (!isCacheEnabled()) {
    return null;
  }

  try {
    const db = getDb();
    const stmt = db.prepare("SELECT response_json FROM llm_cache WHERE cache_key = ?");
    const row = stmt.get(cacheKey) as { response_json: string } | undefined;
    if (row && row.response_json) {
      const data = JSON.parse(row.response_json);
      return {
        ...data,
        latencyMs: 0,
        costUsd: 0,
      };
    }
  } catch (err) {
    console.warn("Failed to read Task 2 LLM cache:", err);
  }
  return null;
}

export function setCachedResponse(
  cacheKey: string,
  model: string,
  step: string,
  response: LLMResponse,
): void {
  if (!isCacheEnabled()) {
    return;
  }

  try {
    const db = getDb();
    const stmt = db.prepare(`
      INSERT OR REPLACE INTO llm_cache (cache_key, model, step, response_json, created_at)
      VALUES (?, ?, ?, ?, ?)
    `);
    stmt.run(cacheKey, model, step, JSON.stringify(response), Date.now() / 1000);
  } catch (err) {
    console.warn("Failed to write Task 2 LLM cache:", err);
  }
}
