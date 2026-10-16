import { describe, it, expect, vi, beforeEach } from "vitest";
import { ClaudeProvider } from "../src/lib/llm/claude";

describe("Task 2 ClaudeProvider with mocked SDK", () => {
  beforeEach(() => {
    vi.resetModules();
    process.env.LLM_CACHE_ENABLED = "false";
  });

  it("returns successful response on valid SDK call", async () => {
    vi.doMock("@anthropic-ai/sdk", () => {
      return {
        default: vi.fn().mockImplementation(() => ({
          messages: {
            create: vi.fn().mockResolvedValue({
              content: [{ type: "text", text: "Mock Claude draft reply" }],
              usage: { input_tokens: 150, output_tokens: 60 },
            }),
          },
        })),
      };
    });

    const provider = new ClaudeProvider("claude-test-model", "test-key");
    const resp = await provider.generate("Draft an email reply", "You are an assistant");

    expect(resp.text).toBe("Mock Claude draft reply");
    expect(resp.inputTokens).toBe(150);
    expect(resp.outputTokens).toBe(60);
    expect(resp.provider).toBe("claude");
  });

  it("maps 429 rate limit errors to RATE_LIMITED code", async () => {
    vi.doMock("@anthropic-ai/sdk", () => {
      return {
        default: vi.fn().mockImplementation(() => ({
          messages: {
            create: vi.fn().mockRejectedValue(new Error("429 rate_limit: tokens per minute exceeded")),
          },
        })),
      };
    });

    const provider = new ClaudeProvider("claude-test-model", "test-key");
    await expect(provider.generate("Prompt")).rejects.toMatchObject({
      code: "RATE_LIMITED",
    });
  });

  it("maps credit / balance exhaustion to QUOTA_EXHAUSTED code", async () => {
    vi.doMock("@anthropic-ai/sdk", () => {
      return {
        default: vi.fn().mockImplementation(() => ({
          messages: {
            create: vi.fn().mockRejectedValue(new Error("429 credit balance too low, quota exceeded")),
          },
        })),
      };
    });

    const provider = new ClaudeProvider("claude-test-model", "test-key");
    await expect(provider.generate("Prompt")).rejects.toMatchObject({
      code: "QUOTA_EXHAUSTED",
    });
  });

  it("maps 529 overloaded error to LLM_UNAVAILABLE code", async () => {
    vi.doMock("@anthropic-ai/sdk", () => {
      return {
        default: vi.fn().mockImplementation(() => ({
          messages: {
            create: vi.fn().mockRejectedValue(new Error("529 Overloaded: Anthropic API is overloaded")),
          },
        })),
      };
    });

    const provider = new ClaudeProvider("claude-test-model", "test-key");
    await expect(provider.generate("Prompt")).rejects.toMatchObject({
      code: "LLM_UNAVAILABLE",
    });
  });

  it("maps connection timeout to TIMEOUT code", async () => {
    vi.doMock("@anthropic-ai/sdk", () => {
      return {
        default: vi.fn().mockImplementation(() => ({
          messages: {
            create: vi.fn().mockRejectedValue(new Error("Connection timeout after 30000ms")),
          },
        })),
      };
    });

    const provider = new ClaudeProvider("claude-test-model", "test-key");
    await expect(provider.generate("Prompt")).rejects.toMatchObject({
      code: "TIMEOUT",
    });
  });

  it("throws LLM_UNAVAILABLE when API key is missing", async () => {
    const provider = new ClaudeProvider("claude-test-model", "");
    await expect(provider.generate("Prompt")).rejects.toMatchObject({
      code: "LLM_UNAVAILABLE",
    });
  });
});
