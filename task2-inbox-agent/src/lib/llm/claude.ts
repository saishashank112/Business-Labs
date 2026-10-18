import { LLMClient, LLMResponse } from "./interface";
import { logLlmCall } from "./logger";
import { checkClaudeBudget, recordClaudeCall } from "./budget";

export class ClaudeProvider implements LLMClient {
  private modelName: string;
  private apiKey: string;

  constructor(modelName?: string, apiKey?: string) {
    this.modelName = modelName || process.env.T2_CLAUDE_MODEL || process.env.CLAUDE_MODEL_FAST || "claude-haiku-5-5";
    this.apiKey = apiKey || process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || "";
  }

  async generate(
    prompt: string,
    systemPrompt?: string,
    requestId?: string,
    step: string = "generate",
  ): Promise<LLMResponse> {
    // Check response cache if enabled
    const { computeCacheKey, getCachedResponse, setCachedResponse } = await import("./cache");
    const cacheKey = computeCacheKey(this.modelName, step, systemPrompt || "", prompt);
    const cached = getCachedResponse(cacheKey);
    if (cached) {
      return cached;
    }

    if (!this.apiKey) {
      const err: any = new Error("ANTHROPIC_API_KEY is not set in environment.");
      err.code = "LLM_UNAVAILABLE";
      throw err;
    }

    checkClaudeBudget();

    const startTime = Date.now();

    try {
      const Anthropic = (await import("@anthropic-ai/sdk")).default;
      const client = new Anthropic({ apiKey: this.apiKey });

      const response = await client.messages.create({
        model: this.modelName,
        max_tokens: 4096,
        system: systemPrompt,
        messages: [{ role: "user", content: prompt }],
      });

      const latencyMs = Date.now() - startTime;
      let text = "";
      for (const block of response.content) {
        if (block.type === "text") {
          text += block.text;
        }
      }

      const inputTokens = response.usage.input_tokens || 0;
      const outputTokens = response.usage.output_tokens || 0;
      const costUsd = recordClaudeCall("task2", step, this.modelName, inputTokens, outputTokens, requestId);

      const result: LLMResponse = {
        text,
        inputTokens,
        outputTokens,
        latencyMs,
        costUsd,
        model: this.modelName,
        provider: "claude",
      };

      setCachedResponse(cacheKey, this.modelName, step, result);
      logLlmCall(requestId, step, this.modelName, "claude", inputTokens, outputTokens, latencyMs, costUsd);

      return result;
    } catch (err: any) {
      const errMsg = (err.message || String(err)).toLowerCase();
      const mappedErr: any = new Error(err.message || "Claude generation failed");

      if (errMsg.includes("rate_limit") || errMsg.includes("429")) {
        mappedErr.code = (errMsg.includes("credit") || errMsg.includes("quota") || errMsg.includes("balance") || errMsg.includes("perday"))
          ? "QUOTA_EXHAUSTED"
          : "RATE_LIMITED";
      } else if (errMsg.includes("overloaded") || errMsg.includes("529") || errMsg.includes("503") || errMsg.includes("unavailable")) {
        mappedErr.code = "LLM_UNAVAILABLE";
      } else if (errMsg.includes("timeout") || errMsg.includes("connection")) {
        mappedErr.code = "TIMEOUT";
      } else if (errMsg.includes("invalid json")) {
        mappedErr.code = "INVALID_OUTPUT";
      } else {
        mappedErr.code = err.code || "INTERNAL_ERROR";
      }

      throw mappedErr;
    }
  }
}
