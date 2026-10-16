import fs from "node:fs";
import path from "node:path";
import { Classification, ClassificationSchema, EmailMessage } from "./schemas";
import { getLLMClient } from "./llm/factory";

let cachedPrompt: string | null = null;

function loadClassifyPrompt(): string {
  if (cachedPrompt) return cachedPrompt;
  const promptPath = path.resolve(process.cwd(), "prompts", "classify_v1.md");
  if (fs.existsSync(promptPath)) {
    cachedPrompt = fs.readFileSync(promptPath, "utf-8");
  } else {
    cachedPrompt = "Classify this email into category, risk_level, urgency, and knowledge_query.";
  }
  return cachedPrompt;
}

export async function classifyEmail(
  email: { subject: string; body: string; from?: string },
  requestId?: string,
): Promise<Classification> {
  const llm = getLLMClient("classify");
  const systemPrompt = loadClassifyPrompt();

  const userPrompt = `
INCOMING EMAIL:
From: ${email.from || "unknown"}
Subject: ${email.subject}
Body:
${email.body}

Please classify this email and respond with ONLY the requested JSON object.
`;

  try {
    const response = await llm.generate(userPrompt, systemPrompt, requestId, "classify");
    let cleaned = response.text.trim();
    if (cleaned.startsWith("```")) {
      const lines = cleaned.split("\n");
      cleaned = lines.slice(1, -1).join("\n").trim();
    }

    const parsedJson = JSON.parse(cleaned);
    return ClassificationSchema.parse(parsedJson);
  } catch (err) {
    console.warn("Classification parse fallback:", err);
    // Safe deterministic fallback based on keywords if LLM output fails
    const lower = `${email.subject} ${email.body}`.toLowerCase();
    let category: any = "how-to";
    let risk: any = "low";
    let urgency: any = "low";

    if (lower.includes("refund") || lower.includes("cancel") || lower.includes("charge")) {
      category = "refund";
      risk = "high";
      urgency = "high";
    } else if (lower.includes("error") || lower.includes("broken") || lower.includes("down")) {
      category = "troubleshooting";
      risk = "medium";
      urgency = "high";
    }

    return {
      category,
      subcategory: "general",
      risk_level: risk,
      urgency,
      confidence: 0.7,
      key_facts: ["Rule-based classification fallback"],
      knowledge_query: category === "how-to" ? email.subject : null,
      reasoning: "Keyword matching fallback",
    };
  }
}
