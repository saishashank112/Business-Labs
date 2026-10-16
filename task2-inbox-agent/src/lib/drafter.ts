import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { Classification, DraftReply, DraftReplySchema, SourceRef } from "./schemas";
import { KnowledgeBrainClient, KnowledgeResponse } from "./knowledge-client";
import { checkGuardrails, GuardrailResult } from "./guardrails";
import { saveInteraction } from "./feedback-store";
import { getLLMClient } from "./llm/factory";

let cachedDraftPrompt: string | null = null;

function loadDraftPrompt(): string {
  if (cachedDraftPrompt) return cachedDraftPrompt;
  const promptPath = path.resolve(process.cwd(), "prompts", "draft_reply_v1.md");
  if (fs.existsSync(promptPath)) {
    cachedDraftPrompt = fs.readFileSync(promptPath, "utf-8");
  } else {
    cachedDraftPrompt = "Draft a professional email reply citing documentation and obeying guardrails.";
  }
  return cachedDraftPrompt;
}

export interface PipelineResult {
  interaction_id: string;
  classification: Classification;
  knowledge: KnowledgeResponse | null;
  draft: DraftReply;
  guardrails: GuardrailResult;
  auto_send_eligible: boolean;
}

export async function processEmailPipeline(
  email: { id?: string; subject: string; body: string; from?: string },
  classification: Classification,
): Promise<PipelineResult> {
  const interactionId = email.id || `int-${crypto.randomUUID()}`;
  const knowledgeClient = new KnowledgeBrainClient();

  // 1. Query Knowledge Brain if search query is provided
  let knowledge: KnowledgeResponse | null = null;
  if (classification.knowledge_query) {
    knowledge = await knowledgeClient.query(classification.knowledge_query);
  }

  // 2. Prepare LLM prompt
  const llm = getLLMClient("draft");
  const systemPrompt = loadDraftPrompt();

  let knowledgeSection = "No technical documentation queried for this category.";
  let sources: SourceRef[] = [];
  if (knowledge) {
    if (knowledge.status === "unavailable") {
      knowledgeSection = "KNOWLEDGE SERVICE STATUS: Knowledge service unavailable. Do not fabricate technical instructions.";
    } else {
      knowledgeSection = `
RETRIEVED KNOWLEDGE BRAIN EVIDENCE:
Status: ${knowledge.status}
Verified Answer:
${knowledge.answer}

Sources:
${(knowledge.sources || []).map((s) => `- [${s.title}](${s.url})`).join("\n")}
`;
      sources = knowledge.sources || [];
    }
  }

  const userPrompt = `
CUSTOMER EMAIL:
From: ${email.from || "Customer"}
Subject: ${email.subject}
Body:
${email.body}

CLASSIFICATION:
Category: ${classification.category}
Risk Level: ${classification.risk_level}
Urgency: ${classification.urgency}
Key Facts: ${classification.key_facts.join(", ")}

${knowledgeSection}

Please draft a professional, polite response following the strict guardrails.
Output strictly JSON matching the required schema.
`;

  let draft: DraftReply;
  try {
    const response = await llm.generate(userPrompt, systemPrompt, interactionId, "draft");
    let cleaned = response.text.trim();
    if (cleaned.startsWith("```")) {
      const lines = cleaned.split("\n");
      cleaned = lines.slice(1, -1).join("\n").trim();
    }
    const parsed = JSON.parse(cleaned);
    draft = DraftReplySchema.parse(parsed);

    // If sources weren't included in LLM output, attach from knowledge response
    if (draft.sources.length === 0 && sources.length > 0) {
      draft.sources = sources;
    }
  } catch (err) {
    console.warn("Draft generation fallback:", err);
    // Safe deterministic fallback
    let suggestedReply = `Thank you for contacting us regarding "${email.subject}". `;
    if (classification.category === "refund") {
      suggestedReply += "We have received your request regarding billing/cancellation. Your ticket has been transferred to our accounts and billing management team for review. They will reach out to you shortly.";
    } else if (classification.category === "project" || classification.category === "quote") {
      suggestedReply += "We appreciate your interest in custom development. An AI technical consultant will review your specifications and schedule a scoping call.";
    } else if (knowledge && knowledge.answer && knowledge.status === "answered") {
      suggestedReply += knowledge.answer;
    } else {
      suggestedReply += "Our technical support team is reviewing your inquiry and will follow up with detailed instructions.";
    }

    draft = {
      category: classification.category,
      summary: `Inquiry regarding ${email.subject}`,
      suggested_reply: suggestedReply,
      sources,
      risk_level: classification.risk_level,
      needs_human_approval: true,
      next_action: "Review by human operator",
    };
  }

  // 3. Evaluate guardrails
  const guardrails = checkGuardrails(draft, classification);

  // If guardrail fails, ensure needs_human_approval is forced to true
  if (!guardrails.passed) {
    draft.needs_human_approval = true;
  }

  // 4. Save to feedback store
  saveInteraction({
    id: interactionId,
    email_file: email.id || "manual_submission",
    email_subject: email.subject,
    email_body: email.body,
    predicted_category: classification.category,
    predicted_risk: classification.risk_level,
    urgency: classification.urgency,
    knowledge_query: classification.knowledge_query || undefined,
    knowledge_response: knowledge ? JSON.stringify(knowledge) : undefined,
    sources: JSON.stringify(draft.sources),
    draft_text: draft.suggested_reply,
    draft_schema: JSON.stringify(draft),
    model: "gemini-2.0-flash",
    prompt_version: "v1",
    outcome: "pending_review",
    created_at: new Date().toISOString(),
  });

  return {
    interaction_id: interactionId,
    classification,
    knowledge,
    draft,
    guardrails,
    auto_send_eligible: guardrails.autoSendAllowed,
  };
}
