import { describe, it, expect } from "vitest";
import { classifyEmail } from "../src/lib/classifier";

describe("Email Classifier", () => {
  it("classifies technical how-to question accurately", async () => {
    const res = await classifyEmail({
      subject: "How do I configure email forwarders?",
      body: "I created info@mydomain.com and want emails forwarded to my personal Gmail address.",
    });

    expect(res.category).toBe("how-to");
    expect(res.risk_level).toBe("low");
    expect(res.knowledge_query).toBeDefined();
  });

  it("classifies refund demand with high risk", async () => {
    const res = await classifyEmail({
      subject: "I demand a refund immediately",
      body: "Cancel my subscription and refund my $490 charge or I will file a bank dispute.",
    });

    expect(res.category).toBe("refund");
    expect(res.risk_level).toBe("high");
  });

  it("classifies system outage complaint with high risk", async () => {
    const res = await classifyEmail({
      subject: "Our website has been down for 4 hours",
      body: "This delay is completely outrageous. We are losing business by the minute.",
    });

    expect(res.risk_level).toBe("high");
  });
});
