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

export function extractRecipientName(email: { from?: string; body?: string }): string {
  // 1. Check for explicit display name in From header (e.g. "Sarah Jenkins <sarah@foo.com>" or "David Cooper")
  if (email.from) {
    const angleMatch = email.from.match(/^([^<@]+)<[^>]+>/);
    if (angleMatch) {
      const displayName = angleMatch[1].trim().replace(/^["']|["']$/g, "");
      const firstName = displayName.split(/\s+/)[0];
      if (firstName && /^[A-Za-z]+$/.test(firstName) && firstName.length > 1) {
        return firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase();
      }
    }
  }

  // 2. Check for signature in the email body (e.g. "Thanks,\nMarcus" or last line "Marcus")
  if (email.body) {
    const bodyText = email.body.trim();
    // Pattern A: Sign-off keyword followed by a name on the next line or after comma
    const signOffMatch = bodyText.match(
      /(?:thanks|regards|best|sincerely|cheers|warmly|thank you)[,!]?\s*\n+([A-Za-z]+)\b/i
    );
    if (signOffMatch && signOffMatch[1]) {
      const name = signOffMatch[1].trim();
      if (/^[A-Za-z]+$/.test(name) && name.length > 1) {
        return name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
      }
    }

    // Pattern B: Last non-empty line is a single name
    const lines = bodyText.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length > 0) {
      const lastLine = lines[lines.length - 1];
      if (/^[A-Za-z]+$/.test(lastLine) && lastLine.length > 1 && lastLine.length < 20) {
        return lastLine.charAt(0).toUpperCase() + lastLine.slice(1).toLowerCase();
      }
    }
  }

  // 3. Check From header localpart (e.g. "sarah.jenkins@marketinghub.io" -> "Sarah")
  if (email.from) {
    const raw = email.from.replace(/<[^>]+>/, "").trim();
    const localPart = raw.split("@")[0].replace(/[._-]/g, " ").trim();
    const candidate = localPart.split(/\s+/)[0];
    const nonNames = ["support", "info", "help", "contact", "admin", "team", "sales", "billing", "service", "hello"];
    if (
      candidate &&
      /^[A-Za-z]+$/.test(candidate) &&
      candidate.length > 1 &&
      !nonNames.includes(candidate.toLowerCase())
    ) {
      return candidate.charAt(0).toUpperCase() + candidate.slice(1).toLowerCase();
    }
  }

  // 4. Default fallback
  return "there";
}

export async function processEmailPipeline(
  email: { id?: string; subject: string; body: string; from?: string },
  classification: Classification,
): Promise<PipelineResult> {
  const interactionId = email.id || `int-${crypto.randomUUID()}`;
  const recipientName = extractRecipientName(email);
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
    if (knowledge.status === "unavailable" || knowledge.status === "error") {
      knowledgeSection = "KNOWLEDGE SERVICE STATUS: Knowledge service unavailable. Technical documentation could not be verified. Do NOT fabricate technical instructions or settings.";
    } else if (knowledge.status === "insufficient_evidence") {
      knowledgeSection = "KNOWLEDGE SERVICE STATUS: Insufficient evidence in help center documentation. Flag for human domain expert.";
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
Recipient Name: ${recipientName}
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

IMPORTANT INSTRUCTIONS:
1. GREETING: Begin your reply addressing "${recipientName}" (e.g. "Hi ${recipientName},"). Never use a different customer's name.
2. If Knowledge Service is unavailable or insufficient, state honestly that the team is reviewing their technical question with a specialist, and do NOT invent configuration steps.
3. Obey strict guardrails: never promise refunds, specific delivery dates, or custom code commitments.
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

    // Enforce correct recipient greeting
    if (recipientName !== "there") {
      if (
        !draft.suggested_reply.toLowerCase().startsWith(`hi ${recipientName.toLowerCase()}`) &&
        !draft.suggested_reply.toLowerCase().startsWith(`hello ${recipientName.toLowerCase()}`) &&
        !draft.suggested_reply.toLowerCase().startsWith(`dear ${recipientName.toLowerCase()}`)
      ) {
        draft.suggested_reply = draft.suggested_reply.replace(/^(hi|hello|dear)\s+[a-z]+[,:]/i, `Hi ${recipientName},`);
        if (!draft.suggested_reply.toLowerCase().startsWith("hi ") && !draft.suggested_reply.toLowerCase().startsWith("hello ")) {
          draft.suggested_reply = `Hi ${recipientName},\n\n${draft.suggested_reply}`;
        }
      }
    }
  } catch (err) {
    console.warn("Draft generation fallback:", err);
    // Safe deterministic fallback with correct recipient
    let suggestedReply = `Hi ${recipientName},\n\nThank you for reaching out regarding "${email.subject}". `;
    if (classification.category === "refund") {
      suggestedReply += "We have received your inquiry regarding billing/cancellation. Your ticket has been transferred to our accounts and billing management team for authorized review. They will reach out to you shortly.";
    } else if (classification.category === "project" || classification.category === "quote") {
      suggestedReply += "We appreciate your interest in custom development. An AI technical consultant will review your specifications and schedule a scoping call.";
    } else if (knowledge && knowledge.status === "error") {
      suggestedReply += "Our technical knowledge service is currently unavailable. Your request has been queued for human technical review to ensure accurate guidance.";
    } else if (knowledge && knowledge.status === "insufficient_evidence") {
      suggestedReply += "Our documentation team does not have verified steps on file for this specific inquiry. Your ticket has been escalated to a senior technical specialist.";
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

  // Force human approval if Knowledge Brain failed or returned insufficient evidence
  if (knowledge && (knowledge.status === "error" || knowledge.status === "unavailable" || knowledge.status === "insufficient_evidence")) {
    draft.needs_human_approval = true;
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
