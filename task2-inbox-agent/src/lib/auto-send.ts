import { getDb } from "./db";

export interface AutoSendStatus {
  kind: string;
  consecutive_unchanged: number;
  eligible: boolean;
  enabled: boolean;
  disabled_reason?: string;
}

export function computeSimilarity(a: string, b: string): number {
  const normA = a.trim().replace(/\s+/g, " ");
  const normB = b.trim().replace(/\s+/g, " ");
  if (normA === normB) return 1.0;

  // Simple token overlap coefficient
  const wordsA = new Set(normA.toLowerCase().split(" "));
  const wordsB = new Set(normB.toLowerCase().split(" "));
  const intersection = new Set([...wordsA].filter((x) => wordsB.has(x)));
  const union = new Set([...wordsA, ...wordsB]);
  return union.size === 0 ? 1.0 : intersection.size / union.size;
}

export function recordInteractionOutcome(
  kind: string,
  draftText: string,
  finalText: string,
  humanAction: string,
  interactionId: string,
): { eligible: boolean; reset: boolean; consecutive: number } {
  const db = getDb();
  const now = new Date().toISOString();

  // 1. Get or create rule record for kind
  let rule = db
    .prepare("SELECT * FROM auto_send_rules WHERE kind = ?")
    .get(kind) as any;

  if (!rule) {
    db.prepare(
      "INSERT INTO auto_send_rules (kind, consecutive_unchanged, eligible, enabled, updated_at) VALUES (?, 0, 0, 0, ?)",
    ).run(kind, now);
    rule = { kind, consecutive_unchanged: 0, eligible: 0, enabled: 0 };
  }

  // 2. Determine if draft was unchanged
  const similarity = computeSimilarity(draftText, finalText);
  const isUnchanged = similarity >= 0.98 && (humanAction === "approve" || humanAction === "auto_send");

  let newConsecutive = rule.consecutive_unchanged;
  let newEligible = rule.eligible;
  let newEnabled = rule.enabled;
  let disabledReason = rule.disabled_reason;
  let reset = false;

  if (isUnchanged) {
    newConsecutive += 1;
    db.prepare(
      "INSERT INTO auto_send_audit (kind, action, detail, interaction_id, timestamp) VALUES (?, 'increment', ?, ?, ?)",
    ).run(kind, `Count increased to ${newConsecutive} (similarity: ${similarity.toFixed(3)})`, interactionId, now);

    if (newConsecutive >= 20 && !newEligible) {
      newEligible = 1;
      db.prepare(
        "INSERT INTO auto_send_audit (kind, action, detail, interaction_id, timestamp) VALUES (?, 'eligible', 'Reached 20 consecutive unchanged drafts. Eligible for controlled auto-send.', ?, ?)",
      ).run(kind, interactionId, now);
    }
  } else {
    // An edit, rejection, or expert escalation resets counter and disables auto-send!
    reset = true;
    newConsecutive = 0;
    newEligible = 0;
    newEnabled = 0;
    disabledReason = `Counter reset due to human action '${humanAction}' (similarity: ${similarity.toFixed(3)})`;

    db.prepare(
      "INSERT INTO auto_send_audit (kind, action, detail, interaction_id, timestamp) VALUES (?, 'reset', ?, ?, ?)",
    ).run(kind, disabledReason, interactionId, now);
  }

  db.prepare(
    "UPDATE auto_send_rules SET consecutive_unchanged = ?, eligible = ?, enabled = ?, disabled_reason = ?, updated_at = ? WHERE kind = ?",
  ).run(newConsecutive, newEligible, newEnabled, disabledReason || null, now, kind);

  return {
    eligible: newEligible === 1,
    reset,
    consecutive: newConsecutive,
  };
}

export function setAutoSendEnabled(kind: string, enabled: boolean): boolean {
  const db = getDb();
  const rule = db.prepare("SELECT * FROM auto_send_rules WHERE kind = ?").get(kind) as any;
  if (!rule || !rule.eligible) {
    return false; // Can only enable if eligible
  }

  const now = new Date().toISOString();
  db.prepare("UPDATE auto_send_rules SET enabled = ?, updated_at = ? WHERE kind = ?").run(
    enabled ? 1 : 0,
    now,
    kind,
  );

  db.prepare(
    "INSERT INTO auto_send_audit (kind, action, detail, timestamp) VALUES (?, ?, ?, ?)",
  ).run(
    kind,
    enabled ? "enabled" : "disabled",
    enabled ? "User enabled auto-send trial" : "User disabled auto-send",
    now,
  );

  return true;
}

export function getAutoSendRules(): AutoSendStatus[] {
  const db = getDb();
  const rows = db.prepare("SELECT * FROM auto_send_rules ORDER BY kind ASC").all() as any[];
  return rows.map((r) => ({
    kind: r.kind,
    consecutive_unchanged: r.consecutive_unchanged,
    eligible: !!r.eligible,
    enabled: !!r.enabled,
    disabled_reason: r.disabled_reason,
  }));
}
