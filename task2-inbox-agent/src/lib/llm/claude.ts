import { LLMClient, LLMResponse } from "./interface";
import { logLlmCall } from "./logger";

export class ClaudeProvider implements LLMClient {
  private modelName: string;
  private apiKey: string;

  constructor(modelName?: string, apiKey?: string) {
    this.modelName = modelName || "claude-3-5-sonnet-20241022";
    this.apiKey = apiKey || process.env.CLAUDE_API_KEY || "";
  }

  async generate(
    prompt: string,
    systemPrompt?: string,
    requestId?: string,
    step: string = "generate",
  ): Promise<LLMResponse> {
    if (!this.apiKey) {
      throw new Error("CLAUDE_API_KEY is not set in environment.");
    }

    const startTime = Date.now();
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
    const costUsd = (inputTokens / 1_000_000) * 3.0 + (outputTokens / 1_000_000) * 15.0;

    logLlmCall(requestId, step, this.modelName, "claude", inputTokens, outputTokens, latencyMs, costUsd);

    return {
      text,
      inputTokens,
      outputTokens,
      latencyMs,
      costUsd,
      model: this.modelName,
      provider: "claude",
    };
  }
}
