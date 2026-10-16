import { Classification, DraftReply } from "./schemas";

export interface GuardrailResult {
  passed: boolean;
  violations: string[];
  autoSendAllowed: boolean;
  blockedReason?: string;
}

// Patterns forbidden in automated draft text unless authorized
const FORBIDDEN_REFUND_PATTERNS = [
  /we will refund/i,
  /your refund of/i,
  /refund has been processed/i,
  /refund is approved/i,
  /money back guarantee will be applied/i,
  /credit card ending in .* has been credited/i,
];

const FORBIDDEN_PRICE_PROMISES = [
  /we will do this for \$\d+/i,
  /the total cost is \$\d+/i,
  /guaranteed price of \$\d+/i,
];

const FORBIDDEN_DELIVERY_PROMISES = [
  /will be delivered by (tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)/i,
  /guarantee completion within \d+ (hours|days)/i,
];

// Categories that can never auto-send under any circumstances (PRD FR-2.10)
const NEVER_AUTO_SEND_CATEGORIES = ["refund", "complaint"];

export function checkGuardrails(
  draft: DraftReply,
  classification: Classification,
): GuardrailResult {
  const violations: string[] = [];
  const text = draft.suggested_reply;

  // 1. Check for unauthorized refund promises
  for (const pattern of FORBIDDEN_REFUND_PATTERNS) {
    if (pattern.test(text)) {
      violations.push(`Unauthorized refund promise detected matching: ${pattern}`);
    }
  }

  // 2. Check for unauthorized price promises
  for (const pattern of FORBIDDEN_PRICE_PROMISES) {
    if (pattern.test(text)) {
      violations.push(`Unauthorized price commitment detected matching: ${pattern}`);
    }
  }

  // 3. Check for unauthorized delivery promises
  for (const pattern of FORBIDDEN_DELIVERY_PROMISES) {
    if (pattern.test(text)) {
      violations.push(`Unauthorized completion date commitment detected: ${pattern}`);
    }
  }

  // 4. Auto-send eligibility checks
  let autoSendAllowed = true;
  let blockedReason: string | undefined;

  if (violations.length > 0) {
    autoSendAllowed = false;
    blockedReason = `Guardrail violations: ${violations.join("; ")}`;
  } else if (NEVER_AUTO_SEND_CATEGORIES.includes(classification.category)) {
    autoSendAllowed = false;
    blockedReason = `Category "${classification.category}" is strictly barred from auto-sending by security policy.`;
  } else if (classification.risk_level === "high") {
    autoSendAllowed = false;
    blockedReason = "High-risk communications require mandatory human sign-off.";
  } else if (draft.needs_human_approval) {
    autoSendAllowed = false;
    blockedReason = "Draft flagged as requiring human approval.";
  }

  return {
    passed: violations.length === 0,
    violations,
    autoSendAllowed,
    blockedReason,
  };
}
