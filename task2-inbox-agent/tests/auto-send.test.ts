import { describe, it, expect } from "vitest";
import { recordInteractionOutcome, getAutoSendRules, computeSimilarity } from "../src/lib/auto-send";

describe("Auto-Send 20-Draft Rule Engine", () => {
  it("computes text similarity accurately", () => {
    const textA = "Please follow the instructions in our documentation guide.";
    const textB = "  Please follow the instructions in our documentation guide. \n";
    expect(computeSimilarity(textA, textB)).toBe(1.0);

    const edited = "Here is a completely different manual response written by an agent.";
    expect(computeSimilarity(textA, edited)).toBeLessThan(0.5);
  });

  it("increments counter on unchanged drafts and resets to 0 on human edit", () => {
    const kind = `test-category-${Date.now()}:general`;
    const draft = "Here are the setup instructions.";
    const approved = "Here are the setup instructions.";
    const edited = "Here are the setup instructions with manual additions from human.";

    // 1. Send unchanged draft 1
    const res1 = recordInteractionOutcome(kind, draft, approved, "approve", "int-1");
    expect(res1.consecutive).toBe(1);
    expect(res1.reset).toBe(false);

    // 2. Send unchanged draft 2
    const res2 = recordInteractionOutcome(kind, draft, approved, "approve", "int-2");
    expect(res2.consecutive).toBe(2);
    expect(res2.reset).toBe(false);

    // 3. Human makes an edit -> MUST RESET COUNTER TO 0!
    const res3 = recordInteractionOutcome(kind, draft, edited, "edit", "int-3");
    expect(res3.consecutive).toBe(0);
    expect(res3.reset).toBe(true);
    expect(res3.eligible).toBe(false);
  });

  it("reaches eligibility after 20 consecutive unchanged drafts", () => {
    const kind = `twenty-sends-${Date.now()}:general`;
    const draft = "Standard verified response text.";

    let lastResult: any;
    for (let i = 1; i <= 20; i++) {
      lastResult = recordInteractionOutcome(kind, draft, draft, "approve", `int-loop-${i}`);
    }

    expect(lastResult.consecutive).toBe(20);
    expect(lastResult.eligible).toBe(true);
  });

  it("fails if test data appears in the real database (task2.db)", () => {
    const fs = require("node:fs");
    const path = require("node:path");
    const { DatabaseSync } = require("node:sqlite");

    const realDbPath = path.resolve(process.cwd(), "task2.db");
    if (fs.existsSync(realDbPath)) {
      const realDb = new DatabaseSync(realDbPath);
      const leakedRules = realDb.prepare("SELECT kind FROM auto_send_rules WHERE kind LIKE 'test-%' OR kind LIKE 'twenty-sends-%'").all();
      expect(leakedRules.length, `Leaked test rules found in real task2.db: ${JSON.stringify(leakedRules)}`).toBe(0);

      const leakedAudit = realDb.prepare("SELECT id FROM auto_send_audit WHERE kind LIKE 'test-%' OR kind LIKE 'twenty-sends-%'").all();
      expect(leakedAudit.length, `Leaked test audit logs found in real task2.db: ${JSON.stringify(leakedAudit)}`).toBe(0);
    }
  });
});
