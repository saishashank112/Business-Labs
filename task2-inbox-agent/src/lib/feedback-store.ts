import { getDb } from "./db";
import { recordInteractionOutcome } from "./auto-send";

export interface StoredInteraction {
  id: string;
  email_file: string;
  email_subject?: string;
  email_body: string;
  predicted_category?: string;
  predicted_risk?: string;
  urgency?: string;
  knowledge_query?: string;
  knowledge_response?: string;
  sources?: string;
  draft_text?: string;
  draft_schema?: string;
  human_action?: string;
  human_edit?: string;
  correction_reason?: string;
  final_text?: string;
  model?: string;
  prompt_version?: string;
  outcome?: string;
  created_at: string;
  reviewed_at?: string;
}

export function saveInteraction(interaction: StoredInteraction): void {
  const db = getDb();
  db.prepare(`
    INSERT OR REPLACE INTO interactions (
      id, email_file, email_subject, email_body, predicted_category, predicted_risk, urgency,
      knowledge_query, knowledge_response, sources, draft_text, draft_schema, human_action,
      human_edit, correction_reason, final_text, model, prompt_version, outcome, created_at, reviewed_at
    ) VALUES (
      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    )
  `).run(
    interaction.id,
    interaction.email_file,
    interaction.email_subject || null,
    interaction.email_body,
    interaction.predicted_category || null,
    interaction.predicted_risk || null,
    interaction.urgency || null,
    interaction.knowledge_query || null,
    interaction.knowledge_response || null,
    interaction.sources || null,
    interaction.draft_text || null,
    interaction.draft_schema || null,
    interaction.human_action || null,
    interaction.human_edit || null,
    interaction.correction_reason || null,
    interaction.final_text || null,
    interaction.model || "gemini-2.0-flash",
    interaction.prompt_version || "v1",
    interaction.outcome || "pending_review",
    interaction.created_at,
    interaction.reviewed_at || null,
  );
}

export function recordHumanReview(
  interactionId: string,
  action: "approve" | "edit" | "reject" | "expert",
  editedText?: string,
  correctionReason?: string,
): { outcome: string; autoSendEligible: boolean; consecutive: number } {
  const db = getDb();
  const row = db.prepare("SELECT * FROM interactions WHERE id = ?").get(interactionId) as any;
  if (!row) {
    throw new Error(`Interaction ${interactionId} not found`);
  }

  const now = new Date().toISOString();
  let finalText = row.draft_text;
  let outcome = "sent";

  if (action === "edit") {
    finalText = editedText || row.draft_text;
    outcome = "edited_and_sent";
  } else if (action === "reject") {
    finalText = editedText || "[Rejected by Operator]";
    outcome = "rejected";
  } else if (action === "expert") {
    finalText = "[Escalated to Subject Matter Expert]";
    outcome = "escalated";
  }

  db.prepare(`
    UPDATE interactions
    SET human_action = ?, human_edit = ?, correction_reason = ?, final_text = ?, outcome = ?, reviewed_at = ?
    WHERE id = ?
  `).run(action, editedText || null, correctionReason || null, finalText, outcome, now, interactionId);

  // Update auto-send rule engine
  const kind = `${row.predicted_category || "general"}:general`;
  const autoResult = recordInteractionOutcome(
    kind,
    row.draft_text || "",
    finalText,
    action,
    interactionId,
  );

  return {
    outcome,
    autoSendEligible: autoResult.eligible,
    consecutive: autoResult.consecutive,
  };
}

export function listInteractions(limit: number = 50): StoredInteraction[] {
  const db = getDb();
  return db
    .prepare("SELECT * FROM interactions ORDER BY created_at DESC LIMIT ?")
    .all(limit) as StoredInteraction[];
}
