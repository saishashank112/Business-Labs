import { LLMClient, LLMResponse } from "./interface";
import { logLlmCall } from "./logger";

export class GeminiProvider implements LLMClient {
  private modelName: string;
  private apiKey: string;

  constructor(modelName?: string, apiKey?: string) {
    this.modelName = modelName || process.env.T2_DRAFT_MODEL || "gemini-3.8-flash";
    this.apiKey = apiKey || process.env.GEMINI_API_KEY || "";
  }

  async generate(
    prompt: string,
    systemPrompt?: string,
    requestId?: string,
    step: string = "generate",
  ): Promise<LLMResponse> {
    if (!this.apiKey) {
      throw new Error("GEMINI_API_KEY is not set in environment.");
    }

    const startTime = Date.now();
    const { GoogleGenAI } = await import("@google/genai");
    const ai = new GoogleGenAI({ apiKey: this.apiKey });

    const contents = prompt;
    const config: any = {};
    if (systemPrompt) {
      config.systemInstruction = systemPrompt;
    }

    const response = await ai.models.generateContent({
      model: this.modelName,
      contents,
      config,
    });

    const latencyMs = Date.now() - startTime;
    const text = response.text || "";
    const inputTokens = (response as any).usageMetadata?.promptTokenCount || 0;
    const outputTokens = (response as any).usageMetadata?.candidatesTokenCount || 0;
    const costUsd = (inputTokens / 1_000_000) * 0.1 + (outputTokens / 1_000_000) * 0.4;

    logLlmCall(requestId, step, this.modelName, "gemini", inputTokens, outputTokens, latencyMs, costUsd);

    return {
      text,
      inputTokens,
      outputTokens,
      latencyMs,
      costUsd,
      model: this.modelName,
      provider: "gemini",
    };
  }
}
