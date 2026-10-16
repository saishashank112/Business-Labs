import { describe, it, expect } from "vitest";
import { checkGuardrails } from "../src/lib/guardrails";
import { Classification, DraftReply } from "../src/lib/schemas";

describe("Guardrails System", () => {
  const baseClassification: Classification = {
    category: "how-to",
    subcategory: "general",
    risk_level: "low",
    urgency: "low",
    confidence: 0.9,
    key_facts: ["Test"],
    knowledge_query: "test",
    reasoning: "none",
  };

  const safeDraft: DraftReply = {
    category: "how-to",
    summary: "Instructions provided",
    suggested_reply: "You can configure this in Settings > General Settings.",
    sources: [{ title: "Settings Guide", url: "https://support.brilliantdirectories.com" }],
    risk_level: "low",
    needs_human_approval: false,
    next_action: "Send",
  };

  it("passes safe technical draft without unauthorized promises", () => {
    const res = checkGuardrails(safeDraft, baseClassification);
    expect(res.passed).toBe(true);
    expect(res.violations).toHaveLength(0);
    expect(res.autoSendAllowed).toBe(true);
  });

  it("detects and flags unauthorized refund promises", () => {
    const refundDraft: DraftReply = {
      ...safeDraft,
      suggested_reply: "We apologize for the issue. We will refund your $45 charge immediately.",
    };
    const res = checkGuardrails(refundDraft, baseClassification);
    expect(res.passed).toBe(false);
    expect(res.violations.some((v) => v.includes("refund"))).toBe(true);
    expect(res.autoSendAllowed).toBe(false);
  });

  it("detects and flags unauthorized price commitments", () => {
    const priceDraft: DraftReply = {
      ...safeDraft,
      suggested_reply: "We will do this for $500 total cost.",
    };
    const res = checkGuardrails(priceDraft, baseClassification);
    expect(res.passed).toBe(false);
    expect(res.violations.some((v) => v.includes("price"))).toBe(true);
    expect(res.autoSendAllowed).toBe(false);
  });

  it("strictly bars refund category from auto-sending even with safe text", () => {
    const refundCategoryClass: Classification = {
      ...baseClassification,
      category: "refund",
      risk_level: "high",
    };
    const res = checkGuardrails(safeDraft, refundCategoryClass);
    expect(res.autoSendAllowed).toBe(false);
    expect(res.blockedReason).toContain("strictly barred from auto-sending");
  });

  it("strictly bars complaint category from auto-sending", () => {
    const complaintClass: Classification = {
      ...baseClassification,
      category: "complaint",
      risk_level: "high",
    };
    const res = checkGuardrails(safeDraft, complaintClass);
    expect(res.autoSendAllowed).toBe(false);
  });
});
