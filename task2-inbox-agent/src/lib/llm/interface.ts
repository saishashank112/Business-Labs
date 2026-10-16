export interface LLMResponse {
  text: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
  costUsd: number;
  model: string;
  provider: string;
}

export interface LLMClient {
  generate(
    prompt: string,
    systemPrompt?: string,
    requestId?: string,
    step?: string,
  ): Promise<LLMResponse>;
}
