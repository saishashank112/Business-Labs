import { LLMClient, LLMResponse } from "./interface";
import { GeminiProvider } from "./gemini";
import { ClaudeProvider } from "./claude";

export class MockLLMClient implements LLMClient {
  async generate(
    prompt: string,
    systemPrompt?: string,
    requestId?: string,
    step: string = "mock",
  ): Promise<LLMResponse> {
    // If prompt is for classification, return valid JSON classification
    if (prompt.toLowerCase().includes("category") || step.includes("classify")) {
      const lower = prompt.toLowerCase();
      let category = "how-to";
      let risk = "low";
      let urgency = "low";
      let query = "general settings";

      if (lower.includes("refund") || lower.includes("cancel") || lower.includes("dispute") || lower.includes("charge")) {
        category = "refund";
        risk = "high";
        urgency = "high";
        query = null as any;
      } else if (lower.includes("complaint") || lower.includes("delay") || lower.includes("unacceptable") || lower.includes("outrageous") || lower.includes("outage")) {
        category = "complaint";
        risk = "high";
        urgency = "high";
        query = null as any;
      } else if (lower.includes("error") || lower.includes("down") || lower.includes("broken") || lower.includes("slow") || lower.includes("failed")) {
        category = "troubleshooting";
        risk = "medium";
        urgency = "high";
        query = "troubleshooting error";
      } else if (lower.includes("quote") || lower.includes("cost") || lower.includes("pricing") || lower.includes("estimate") || lower.includes("rate")) {
        category = "quote";
        risk = "medium";
        urgency = "medium";
        query = null as any;
      } else if (lower.includes("hire") || lower.includes("build") || lower.includes("develop") || lower.includes("custom") || lower.includes("redesign")) {
        category = "project";
        risk = "medium";
        urgency = "medium";
        query = null as any;
      } else if (lower.includes("following up") || lower.includes("status of") || lower.includes("any update")) {
        category = "follow-up";
        risk = "low";
        urgency = "medium";
        query = null as any;
      }

      if (lower.includes("mass email")) query = "mass email campaign";
      if (lower.includes("forwarder")) query = "email forwarders";
      if (lower.includes("import categories") || lower.includes("csv")) query = "import categories csv";
      if (lower.includes("ssl")) query = "ssl https";

      return {
        text: JSON.stringify({
          category,
          subcategory: "general",
          risk_level: risk,
          urgency,
          confidence: 0.95,
          key_facts: ["Analyzed via Mock client"],
          knowledge_query: query,
          reasoning: "Rule-based mock determination for testing",
        }),
        inputTokens: 50,
        outputTokens: 60,
        latencyMs: 15,
        costUsd: 0.0,
        model: "mock-llm",
        provider: "mock",
      };
    }

    // Default mock response for draft reply
    return {
      text: JSON.stringify({
        category: "how-to",
        summary: "Provided documentation instructions for customer request.",
        suggested_reply:
          "Thank you for contacting us. According to our documentation, you can configure this in your Brilliant Directories admin settings. Please see the referenced documentation guide for details.",
        sources: [
          {
            title: "Brilliant Directories Documentation",
            url: "https://support.brilliantdirectories.com",
          },
        ],
        risk_level: "low",
        needs_human_approval: false,
        next_action: "Send response to customer",
      }),
      inputTokens: 100,
      outputTokens: 75,
      latencyMs: 20,
      costUsd: 0.0,
      model: "mock-llm",
      provider: "mock",
    };
  }
}

export function getLLMClient(step: string = "draft"): LLMClient {
  const profile = (process.env.PROFILE || "dev").toLowerCase();

  // In final profile, Claude handles core reasoning if configured
  if (profile === "final" && process.env.CLAUDE_API_KEY && (step === "draft" || step === "classify")) {
    return new ClaudeProvider();
  }

  if (process.env.GEMINI_API_KEY) {
    return new GeminiProvider();
  }

  if (process.env.CLAUDE_API_KEY) {
    return new ClaudeProvider();
  }

  return new MockLLMClient();
}
