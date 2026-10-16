"use client";

import React, { useState, useEffect } from "react";

interface EmailItem {
  id: string;
  subject: string;
  from: string;
  body: string;
  expected_category?: string;
  expected_risk?: string;
  expected_urgency?: string;
  is_holdout?: boolean;
}

interface PipelineData {
  interaction_id: string;
  classification: {
    category: string;
    subcategory: string;
    risk_level: string;
    urgency: string;
    confidence: number;
    key_facts: string[];
    knowledge_query?: string;
    reasoning?: string;
  };
  knowledge: {
    status: string;
    answer: string;
    sources: Array<{ title: string; url: string; relevance?: number }>;
  } | null;
  draft: {
    category: string;
    summary: string;
    suggested_reply: string;
    sources: Array<{ title: string; url: string }>;
    risk_level: string;
    needs_human_approval: boolean;
  };
  guardrails: {
    passed: boolean;
    violations: string[];
    autoSendAllowed: boolean;
    blockedReason?: string;
  };
}

export default function InboxReviewPage() {
  const [emails, setEmails] = useState<EmailItem[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<EmailItem | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [pipelineData, setPipelineData] = useState<PipelineData | null>(null);
  const [draftText, setDraftText] = useState<string>("");
  const [correctionReason, setCorrectionReason] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [reviewMessage, setReviewMessage] = useState<string | null>(null);
  const [autoSendRules, setAutoSendRules] = useState<any[]>([]);

  // Load emails and auto-send rules on mount
  useEffect(() => {
    fetch("/api/emails")
      .then((res) => res.json())
      .then((data) => {
        if (data.emails && data.emails.length > 0) {
          setEmails(data.emails);
          setSelectedEmail(data.emails[0]);
        }
      })
      .catch(console.error);

    fetchAutoSendRules();
  }, []);

  const fetchAutoSendRules = () => {
    fetch("/api/auto-send")
      .then((res) => res.json())
      .then((d) => setAutoSendRules(d.rules || []))
      .catch(console.error);
  };

  // When selected email changes, run or reset pipeline
  useEffect(() => {
    if (selectedEmail) {
      handleRunPipeline(selectedEmail);
    }
  }, [selectedEmail?.id]);

  const handleRunPipeline = async (email: EmailItem) => {
    setLoading(true);
    setReviewMessage(null);
    try {
      const res = await fetch("/api/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(email),
      });
      const data = await res.json();
      if (res.ok) {
        setPipelineData(data);
        setDraftText(data.draft?.suggested_reply || "");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleReviewAction = async (action: "approve" | "edit" | "reject" | "expert") => {
    if (!pipelineData) return;
    setLoading(true);
    try {
      const res = await fetch("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interaction_id: pipelineData.interaction_id,
          action,
          edited_text: draftText,
          correction_reason: correctionReason,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setReviewMessage(
          `Action '${action}' applied: ${data.message} | Consecutive unchanged sends for kind: ${data.consecutive}/20`,
        );
        fetchAutoSendRules();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredEmails = emails.filter((e) => {
    if (filterCategory === "all") return true;
    if (filterCategory === "holdout") return !!e.is_holdout;
    return e.expected_category === filterCategory;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      {/* Top Header */}
      <header
        style={{
          padding: "1rem 2rem",
          background: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border-color)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h1
            style={{
              fontSize: "1.4rem",
              fontWeight: 700,
              background: "linear-gradient(90deg, #3b82f6, #8b5cf6)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Inbox Agent — Human Review System
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
            AI Customer Support Triage, Typed Knowledge Brain Integration & 20-Draft Auto-Send Rule Engine
          </p>
        </div>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <span
            style={{
              fontSize: "0.8rem",
              background: "#1e293b",
              border: "1px solid #334155",
              padding: "4px 12px",
              borderRadius: "20px",
            }}
          >
            Dataset: {emails.length} Emails (15 Hold-out)
          </span>
          <span
            style={{
              fontSize: "0.8rem",
              background: "#10b98122",
              color: "#10b981",
              border: "1px solid #10b98155",
              padding: "4px 12px",
              borderRadius: "20px",
            }}
          >
            Task 1 HTTP Client: Connected
          </span>
        </div>
      </header>

      {/* Main Container */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left Column: Email List */}
        <div
          style={{
            width: "380px",
            borderRight: "1px solid var(--border-color)",
            background: "var(--bg-secondary)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Filters */}
          <div style={{ padding: "0.75rem 1rem", borderBottom: "1px solid var(--border-color)" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>
              Filter by Category
            </label>
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              style={{
                width: "100%",
                padding: "6px 10px",
                marginTop: "4px",
                background: "var(--bg-card)",
                color: "var(--text-primary)",
                border: "1px solid var(--border-color)",
                borderRadius: "6px",
              }}
            >
              <option value="all">All Categories ({emails.length})</option>
              <option value="how-to">How-To</option>
              <option value="troubleshooting">Troubleshooting</option>
              <option value="project">Project Request</option>
              <option value="refund">Refund / Cancellation</option>
              <option value="complaint">Complaint</option>
              <option value="quote">Quote Request</option>
              <option value="follow-up">Follow-Up</option>
              <option value="holdout">Hold-out Eval Set</option>
            </select>
          </div>

          {/* Email Items Scrollable */}
          <div style={{ flex: 1, overflowY: "auto" }}>
            {filteredEmails.map((email) => {
              const isSelected = selectedEmail?.id === email.id;
              const isRefund = email.expected_category === "refund" || email.expected_risk === "high";
              return (
                <div
                  key={email.id}
                  onClick={() => setSelectedEmail(email)}
                  style={{
                    padding: "0.85rem 1rem",
                    borderBottom: "1px solid var(--border-color)",
                    cursor: "pointer",
                    background: isSelected ? "#1e293b" : "transparent",
                    borderLeft: isSelected ? "4px solid #3b82f6" : "4px solid transparent",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{email.id}</span>
                    <div style={{ display: "flex", gap: "4px" }}>
                      {email.is_holdout && (
                        <span
                          style={{
                            fontSize: "0.65rem",
                            background: "#8b5cf633",
                            color: "#c084fc",
                            padding: "2px 6px",
                            borderRadius: "10px",
                          }}
                        >
                          Hold-out
                        </span>
                      )}
                      <span
                        style={{
                          fontSize: "0.65rem",
                          background: isRefund ? "#ef444433" : "#3b82f633",
                          color: isRefund ? "#fca5a5" : "#93c5fd",
                          padding: "2px 6px",
                          borderRadius: "10px",
                        }}
                      >
                        {email.expected_category}
                      </span>
                    </div>
                  </div>
                  <div
                    style={{
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      marginBottom: "4px",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {email.subject}
                  </div>
                  <div
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-secondary)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    From: {email.from}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Center / Right Column: Review Workspace */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflowY: "auto", padding: "1.5rem" }}>
          {selectedEmail ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.2rem", maxWidth: "1100px" }}>
              {/* Review Alert message */}
              {reviewMessage && (
                <div
                  style={{
                    padding: "0.75rem 1rem",
                    borderRadius: "8px",
                    background: "#10b98122",
                    border: "1px solid #10b98166",
                    color: "#34d399",
                    fontSize: "0.85rem",
                  }}
                >
                  {reviewMessage}
                </div>
              )}

              {/* Email Content Box */}
              <div
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  padding: "1.2rem",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                  <h2 style={{ fontSize: "1.1rem", fontWeight: 600 }}>{selectedEmail.subject}</h2>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>ID: {selectedEmail.id}</span>
                </div>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.75rem" }}>
                  From: <strong>{selectedEmail.from}</strong>
                </p>
                <div
                  style={{
                    background: "#090d16",
                    padding: "0.9rem",
                    borderRadius: "6px",
                    fontSize: "0.85rem",
                    lineHeight: 1.5,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {selectedEmail.body}
                </div>
              </div>

              {/* Triage & Knowledge Brain Evidence Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                {/* Classification Card */}
                <div
                  style={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "8px",
                    padding: "1rem",
                  }}
                >
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.75rem", color: "#60a5fa" }}>
                    🎯 Classification & Risk
                  </h3>
                  {pipelineData ? (
                    <div style={{ fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                      <div>
                        <strong>Category:</strong>{" "}
                        <span style={{ textTransform: "capitalize", color: "#93c5fd" }}>
                          {pipelineData.classification.category}
                        </span>
                      </div>
                      <div>
                        <strong>Risk Level:</strong>{" "}
                        <span
                          style={{
                            color:
                              pipelineData.classification.risk_level === "high"
                                ? "#ef4444"
                                : pipelineData.classification.risk_level === "medium"
                                ? "#f59e0b"
                                : "#10b981",
                            fontWeight: 600,
                            textTransform: "uppercase",
                          }}
                        >
                          {pipelineData.classification.risk_level}
                        </span>
                      </div>
                      <div>
                        <strong>Urgency:</strong> {pipelineData.classification.urgency}
                      </div>
                      <div>
                        <strong>Knowledge Query:</strong>{" "}
                        <code>{pipelineData.classification.knowledge_query || "None"}</code>
                      </div>
                    </div>
                  ) : (
                    <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Analyzing...</p>
                  )}
                </div>

                {/* Knowledge Evidence Card */}
                <div
                  style={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "8px",
                    padding: "1rem",
                  }}
                >
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.75rem", color: "#a78bfa" }}>
                    🧠 Task 1 Knowledge Brain (HTTP)
                  </h3>
                  {pipelineData?.knowledge ? (
                    <div style={{ fontSize: "0.85rem" }}>
                      <div style={{ marginBottom: "0.4rem" }}>
                        <strong>Status:</strong>{" "}
                        <span style={{ color: pipelineData.knowledge.status === "answered" ? "#10b981" : "#f59e0b" }}>
                          {pipelineData.knowledge.status}
                        </span>
                      </div>
                      <p style={{ color: "var(--text-secondary)", maxHeight: "100px", overflowY: "auto", fontSize: "0.8rem", lineHeight: 1.4 }}>
                        {pipelineData.knowledge.answer}
                      </p>
                      {pipelineData.knowledge.sources?.length > 0 && (
                        <div style={{ marginTop: "0.5rem" }}>
                          <strong>Sources:</strong>
                          {pipelineData.knowledge.sources.map((s, idx) => (
                            <div key={idx} style={{ fontSize: "0.75rem" }}>
                              🔗 <a href={s.url} target="_blank" rel="noreferrer" style={{ color: "#60a5fa" }}>{s.title}</a>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                      No Task 1 query needed or service idle.
                    </p>
                  )}
                </div>
              </div>

              {/* Guardrails Card */}
              {pipelineData?.guardrails && (
                <div
                  style={{
                    padding: "0.75rem 1rem",
                    borderRadius: "8px",
                    background: pipelineData.guardrails.passed ? "#10b98115" : "#ef444422",
                    border: pipelineData.guardrails.passed ? "1px solid #10b98144" : "1px solid #ef444466",
                    fontSize: "0.85rem",
                  }}
                >
                  <strong>🛡️ Guardrail Status: </strong>
                  {pipelineData.guardrails.passed ? (
                    <span style={{ color: "#34d399" }}>Passed — No unauthorized promises or violations.</span>
                  ) : (
                    <span style={{ color: "#f87171" }}>
                      Violations Detected: {pipelineData.guardrails.violations.join("; ")}
                    </span>
                  )}
                  {pipelineData.guardrails.blockedReason && (
                    <div style={{ marginTop: "4px", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      Auto-send restriction: {pipelineData.guardrails.blockedReason}
                    </div>
                  )}
                </div>
              )}

              {/* AI Draft Response & Human Review Actions */}
              <div
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  padding: "1.2rem",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                  <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Draft Response (Review & Edit)</h3>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    Sending is simulated and audit-logged
                  </span>
                </div>
                <textarea
                  value={draftText}
                  onChange={(e) => setDraftText(e.target.value)}
                  rows={6}
                  style={{
                    width: "100%",
                    padding: "0.75rem",
                    background: "#090d16",
                    color: "var(--text-primary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "6px",
                    fontSize: "0.9rem",
                    lineHeight: 1.5,
                    marginBottom: "0.75rem",
                  }}
                />

                <input
                  type="text"
                  placeholder="Correction reason (optional, recorded in feedback store)"
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "6px 10px",
                    background: "#090d16",
                    color: "var(--text-primary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "6px",
                    fontSize: "0.85rem",
                    marginBottom: "1rem",
                  }}
                />

                {/* Action Buttons */}
                <div style={{ display: "flex", gap: "0.75rem" }}>
                  <button
                    onClick={() => handleReviewAction("approve")}
                    disabled={loading}
                    style={{
                      background: "#10b981",
                      color: "white",
                      border: "none",
                      padding: "8px 16px",
                      borderRadius: "6px",
                      fontWeight: 600,
                      cursor: "pointer",
                      fontSize: "0.85rem",
                    }}
                  >
                    ✅ Approve & Send
                  </button>
                  <button
                    onClick={() => handleReviewAction("edit")}
                    disabled={loading}
                    style={{
                      background: "#3b82f6",
                      color: "white",
                      border: "none",
                      padding: "8px 16px",
                      borderRadius: "6px",
                      fontWeight: 600,
                      cursor: "pointer",
                      fontSize: "0.85rem",
                    }}
                  >
                    ✏️ Edit & Send
                  </button>
                  <button
                    onClick={() => handleReviewAction("reject")}
                    disabled={loading}
                    style={{
                      background: "#ef4444",
                      color: "white",
                      border: "none",
                      padding: "8px 16px",
                      borderRadius: "6px",
                      fontWeight: 600,
                      cursor: "pointer",
                      fontSize: "0.85rem",
                    }}
                  >
                    ❌ Reject & Write Own
                  </button>
                  <button
                    onClick={() => handleReviewAction("expert")}
                    disabled={loading}
                    style={{
                      background: "#8b5cf6",
                      color: "white",
                      border: "none",
                      padding: "8px 16px",
                      borderRadius: "6px",
                      fontWeight: 600,
                      cursor: "pointer",
                      fontSize: "0.85rem",
                    }}
                  >
                    🚨 Mark Needs Expert
                  </button>
                </div>
              </div>

              {/* 20-Draft Auto-Send Dashboard */}
              <div
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  padding: "1.2rem",
                  marginBottom: "2rem",
                }}
              >
                <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
                  📊 20-Draft Auto-Send Rule Engine Status
                </h3>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginBottom: "1rem" }}>
                  Categories require 20 consecutive unchanged drafts before auto-send eligibility. Refunds and complaints never auto-send.
                </p>

                {autoSendRules.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {autoSendRules.map((rule) => {
                      const pct = Math.min(100, (rule.consecutive_unchanged / 20) * 100);
                      return (
                        <div
                          key={rule.kind}
                          style={{
                            background: "#090d16",
                            padding: "0.75rem",
                            borderRadius: "6px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                          }}
                        >
                          <div style={{ width: "200px" }}>
                            <strong>{rule.kind}</strong>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                              {rule.eligible ? "Eligible" : "Learning"} ({rule.consecutive_unchanged}/20 sends)
                            </div>
                          </div>
                          <div style={{ flex: 1, margin: "0 1.5rem" }}>
                            <div style={{ background: "#1e293b", height: "8px", borderRadius: "4px", overflow: "hidden" }}>
                              <div style={{ width: `${pct}%`, background: rule.eligible ? "#10b981" : "#3b82f6", height: "100%" }} />
                            </div>
                          </div>
                          <div>
                            <span
                              style={{
                                fontSize: "0.75rem",
                                padding: "3px 8px",
                                borderRadius: "12px",
                                background: rule.enabled ? "#10b98133" : "#64748b33",
                                color: rule.enabled ? "#34d399" : "#94a3b8",
                              }}
                            >
                              {rule.enabled ? "Auto-Send Active" : "Human Required"}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    No interaction rules recorded yet. Review emails above to advance the counter.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <p style={{ color: "var(--text-muted)" }}>Select an email from the left sidebar to review.</p>
          )}
        </div>
      </div>
    </div>
  );
}
