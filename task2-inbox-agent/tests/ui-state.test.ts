import { describe, it, expect, vi } from "vitest";
import { processEmailPipeline } from "../src/lib/drafter";
import { Classification } from "../src/lib/schemas";
import { KnowledgeBrainClient } from "../src/lib/knowledge-client";

describe("Email State Isolation and Race Condition Prevention", () => {
  const emailA = {
    id: "email-04",
    from: "clara.oswald@marketinghub.io",
    subject: "Connecting Facebook and Twitter links",
    body: "Hi team,\nWhere can I add our social media links in the settings?\nThanks,\nClara",
  };

  const emailB = {
    id: "email-05",
    from: "marcus.vance@lawfirms.com",
    subject: "How to create staff mailboxes and webmail login",
    body: "Hello,\nWe need to create 5 email mailboxes for our associate attorneys. How do we configure email accounts?\nMarcus",
  };

  const classA: Classification = {
    category: "how-to",
    subcategory: "social_media",
    risk_level: "low",
    urgency: "medium",
    confidence: 0.95,
    key_facts: ["Add social media links in settings"],
    knowledge_query: "social media links general settings",
  };

  const classB: Classification = {
    category: "how-to",
    subcategory: "email_accounts",
    risk_level: "low",
    urgency: "medium",
    confidence: 0.95,
    key_facts: ["Create 5 email accounts for staff"],
    knowledge_query: "create email accounts webmail login",
  };

  it("ensures draft greeting strictly uses the sender of the selected email", async () => {
    vi.spyOn(KnowledgeBrainClient.prototype, "query").mockResolvedValue({
      status: "answered",
      answer: "Configure social media links in Settings > General Settings.",
      sources: [{ title: "Social Media Tab", url: "https://support.brilliantdirectories.com/article" }],
      images: [],
      needs_human: false,
      escalation_id: null,
      request_id: "req-mock",
    });

    const resA = await processEmailPipeline(emailA, classA);
    expect(resA.interaction_id).toBe("email-04");
    expect(resA.draft.suggested_reply.toLowerCase()).toContain("hi clara");
    expect(resA.draft.suggested_reply.toLowerCase()).not.toContain("marcus");

    const resB = await processEmailPipeline(emailB, classB);
    expect(resB.interaction_id).toBe("email-05");
    expect(resB.draft.suggested_reply.toLowerCase()).toContain("hi marcus");
    expect(resB.draft.suggested_reply.toLowerCase()).not.toContain("clara");
  });

  it("simulates slow response for Email A arriving after switching to Email B", async () => {
    // Simulate UI state container
    let activeEmailId = "email-04";
    let displayedDraft: string | null = null;
    let abortControllerA: AbortController | null = new AbortController();

    // 1. User is on Email A, request is launched
    const slowEmailAPromise = new Promise<{ id: string; draft: string }>((resolve, reject) => {
      const timer = setTimeout(() => {
        if (abortControllerA?.signal.aborted) {
          reject(new DOMException("Aborted", "AbortError"));
        } else {
          resolve({ id: "email-04", draft: "Hi Clara, here are your social links..." });
        }
      }, 50);

      abortControllerA?.signal.addEventListener("abort", () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      });
    });

    // 2. User immediately clicks Email B before Email A finishes
    abortControllerA.abort(); // Cancel Email A
    activeEmailId = "email-05";
    displayedDraft = null; // Cleared on switch

    // Email B request finishes fast
    const fastEmailBPromise = Promise.resolve({
      id: "email-05",
      draft: "Hi Marcus, here is how you create staff mailboxes...",
    });

    const resB = await fastEmailBPromise;
    if (activeEmailId === resB.id) {
      displayedDraft = resB.draft;
    }

    expect(displayedDraft).toBe("Hi Marcus, here is how you create staff mailboxes...");

    // 3. Now slow Email A finally rejects/aborts
    let emailAError: any = null;
    try {
      const lateResA = await slowEmailAPromise;
      // Even if it didn't throw, guard prevents updating if activeEmailId != res.id
      if (activeEmailId === lateResA.id) {
        displayedDraft = lateResA.draft;
      }
    } catch (err) {
      emailAError = err;
    }

    // Verify Email A was aborted and did NOT overwrite Email B
    expect(emailAError?.name).toBe("AbortError");
    expect(displayedDraft).toBe("Hi Marcus, here is how you create staff mailboxes...");
    expect(displayedDraft).not.toContain("Clara");
  });

  describe("extractRecipientName", () => {
    it("extracts body signature when From header has no name (Hello team ... Marcus)", async () => {
      const email = {
        from: "info@localhealthpros.com",
        body: "Hello team,\nHow do I create new staff email inboxes under our domain name?\nMarcus",
      };
      const { extractRecipientName } = await import("../src/lib/drafter");
      expect(extractRecipientName(email)).toBe("Marcus");
    });

    it("falls back to 'there' when email has no name in From header or body", async () => {
      const email = {
        from: "support@service.com",
        body: "Is the portal currently undergoing maintenance?",
      };
      const { extractRecipientName } = await import("../src/lib/drafter");
      expect(extractRecipientName(email)).toBe("there");
    });

    it("prefers From header display name when present", async () => {
      const email = {
        from: "Sarah Jenkins <sarah.jenkins@marketinghub.io>",
        body: "Can I send mass email campaigns directly from my dashboard?",
      };
      const { extractRecipientName } = await import("../src/lib/drafter");
      expect(extractRecipientName(email)).toBe("Sarah");
    });
  });

  describe("Task 1 Knowledge Service Resilience", () => {
    it("forces needs_human_approval and shows failure when Task 1 returns status error", async () => {
      vi.spyOn(KnowledgeBrainClient.prototype, "query").mockResolvedValue({
        status: "error",
        error_code: "LLM_UNAVAILABLE",
        answer: "Knowledge service error: Gemini model unavailable",
        sources: [],
        images: [],
        needs_human: true,
        escalation_id: null,
        request_id: "req-err-1",
      });

      const res = await processEmailPipeline(emailA, classA);
      expect(res.knowledge?.status).toBe("error");
      expect(res.draft.needs_human_approval).toBe(true);
      expect(res.draft.suggested_reply.toLowerCase()).toContain("technical knowledge service is currently unavailable");
      expect(res.draft.suggested_reply).not.toContain("Settings > General Settings");
    });

    it("forces needs_human_approval and handles timeout / network error gracefully", async () => {
      vi.spyOn(KnowledgeBrainClient.prototype, "query").mockResolvedValue({
        status: "unavailable",
        answer: "Knowledge Brain API unavailable (timeout).",
        sources: [],
        images: [],
        needs_human: true,
        escalation_id: null,
        request_id: "timeout-req",
      });

      const res = await processEmailPipeline(emailA, classA);
      expect(res.knowledge?.status).toBe("unavailable");
      expect(res.draft.needs_human_approval).toBe(true);
      expect(res.draft.suggested_reply.toLowerCase()).toContain("technical support team is reviewing your inquiry");
    });

    it("forces needs_human_approval when Task 1 returns status insufficient_evidence", async () => {
      vi.spyOn(KnowledgeBrainClient.prototype, "query").mockResolvedValue({
        status: "insufficient_evidence",
        answer: "Documentation does not mention this setting.",
        sources: [],
        images: [],
        needs_human: true,
        escalation_id: "esc-123",
        request_id: "req-insuff",
      });

      const res = await processEmailPipeline(emailB, classB);
      expect(res.knowledge?.status).toBe("insufficient_evidence");
      expect(res.draft.needs_human_approval).toBe(true);
      expect(res.draft.suggested_reply.toLowerCase()).toContain("documentation team does not have verified steps");
    });

    it("forces needs_human_approval when Task 1 returns QUOTA_EXHAUSTED", async () => {
      vi.spyOn(KnowledgeBrainClient.prototype, "query").mockResolvedValue({
        status: "error",
        error_code: "QUOTA_EXHAUSTED",
        answer: "Knowledge service error: Gemini daily quota exhausted",
        sources: [],
        images: [],
        needs_human: true,
        escalation_id: null,
        request_id: "req-quota-1",
      });

      const res = await processEmailPipeline(emailA, classA);
      expect(res.knowledge?.status).toBe("error");
      expect(res.knowledge?.error_code).toBe("QUOTA_EXHAUSTED");
      expect(res.draft.needs_human_approval).toBe(true);
    });

    it("forces needs_human_approval when Task 1 returns RATE_LIMITED", async () => {
      vi.spyOn(KnowledgeBrainClient.prototype, "query").mockResolvedValue({
        status: "error",
        error_code: "RATE_LIMITED",
        answer: "Knowledge service error: 429 Rate limit burst exceeded",
        sources: [],
        images: [],
        needs_human: true,
        escalation_id: null,
        request_id: "req-rate-1",
      });

      const res = await processEmailPipeline(emailA, classA);
      expect(res.knowledge?.status).toBe("error");
      expect(res.knowledge?.error_code).toBe("RATE_LIMITED");
      expect(res.draft.needs_human_approval).toBe(true);
    });

    it("forces needs_human_approval when Task 1 returns INVALID_OUTPUT", async () => {
      vi.spyOn(KnowledgeBrainClient.prototype, "query").mockResolvedValue({
        status: "error",
        error_code: "INVALID_OUTPUT",
        answer: "Knowledge service error: Failed to parse output schema",
        sources: [],
        images: [],
        needs_human: true,
        escalation_id: null,
        request_id: "req-schema-1",
      });

      const res = await processEmailPipeline(emailA, classA);
      expect(res.knowledge?.status).toBe("error");
      expect(res.knowledge?.error_code).toBe("INVALID_OUTPUT");
      expect(res.draft.needs_human_approval).toBe(true);
    });
  });
});

