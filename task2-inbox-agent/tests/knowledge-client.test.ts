import { describe, it, expect } from "vitest";
import { KnowledgeBrainClient } from "../src/lib/knowledge-client";

describe("KnowledgeBrainClient (Task 1 HTTP Client)", () => {
  it("returns clear failure state when Task 1 service is unreachable", async () => {
    // Port 9999 is intentionally unreachable
    const client = new KnowledgeBrainClient("http://127.0.0.1:9999", "test-key", 1000);
    const res = await client.query("How to configure email forwarders?");

    expect(res.success).toBe(false);
    expect(res.status).toBe("unavailable");
    expect(res.answer).toContain("Knowledge service unavailable");
    expect(res.needs_human).toBe(true);
  });
});
