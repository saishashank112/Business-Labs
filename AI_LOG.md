# Engineering Log: AI Tech Consultant

> **Log Purpose:** Transparent record of AI engineering decisions, prompt iterations, guardrail edge cases, and technical trade-offs encountered during the 4-day development of the AI Tech Consultant system.

---

## 1. Prompt Engineering & Iterations

### Iteration 1: Evidence-Only RAG Grounding (`prompts/rag_answer_v1.md`)
- **Initial Problem:** Early tests on Brilliant Directories questions produced hallucinations where the model assumed standard WordPress or Shopify features existed on BD (e.g., claiming WooCommerce plugins could be installed).
- **Prompt Refinement:** Introduced strict negative constraints:
  ```markdown
  CRITICAL RULE: Rely EXCLUSIVELY on the provided <context> articles.
  If the context does not explicitly state that a feature is supported or how to configure it,
  you MUST set status = "insufficient_evidence" and needs_human = true.
  Do NOT assume standard web development practices apply to Brilliant Directories.
  ```
- **Result:** Hallucinations dropped to zero; unanswerable queries cleanly escalate to human domain experts.

### Iteration 2: Guardrail-Enforced Email Drafting (`src/lib/guardrails.ts`)
- **Initial Problem:** Inbound emails expressing frustration or demanding refunds tempted the model to apologize profusely and offer compensatory discounts or promises.
- **Prompt & Rule Refinement:** Implemented a two-tier defense:
  1. System prompt strictly forbade promising refunds, fee waivers, or delivery dates.
  2. Post-generation programmatic guardrail regex scan:
     ```typescript
     const FORBIDDEN_PATTERNS = [
       /refund\s+(has been|will be|is)\s+approved/i,
       /we\s+will\s+refund/i,
       /guarantee\s+launch\s+by/i,
       /free\s+of\s+charge/i,
     ];
     ```
  3. If matched, the draft is stripped of commitments and flagged with `needs_human_approval: true`.
- **Result:** 100% compliance on high-risk emails across the 50-email test dataset.

### Iteration 3: Staged Transcript Extraction (`agents/transcript_analyst.py`)
- **Initial Problem:** Attempting to extract requirements from an entire 45-minute meeting transcript in a single prompt caused the model to miss later items (lost in the middle phenomenon).
- **Prompt Refinement:** Implemented a staged dialogue processor that segments the conversation by speaker turn and timestamp, extracting requirement candidates iteratively before deduplicating.
- **Result:** Requirement recall on role-played Transcripts A, B, and C reached 100%.

---

## 2. Key Architecture Decisions & Technical Trade-Offs

| Decision | Alternative Considered | Chosen Approach | Rationale |
|---|---|---|---|
| **Embeddings Engine** | OpenAI / Cloud Embeddings API | Local ONNX `all-MiniLM-L6-v2` | Zero API cost, zero cloud rate limits, sub-10ms local inference latency, full privacy. |
| **Search Paradigm** | Vector-Only Semantic Search | Hybrid Search (ChromaDB + SQLite FTS5 with RRF) | Pure vector search missed exact technical identifiers (e.g., `TXT records`, `MX records`, `API keys`); FTS5 BM25 handles exact tokens flawlessly. |
| **Node.js SQLite Driver** | `better-sqlite3` | Native Node 22+ `node:sqlite` | Avoids native C++ compilation toolchain failures (`node-gyp` / Python / MSBuild) on Windows while retaining synchronous speed. |
| **Cross-Task Communication** | Shared DB / Direct Code Import | Strictly Decoupled HTTP API (`X-API-Key`) | Satisfies core PRD requirement; ensures independent deployability, scalability, and security boundaries. |
| **Scope Diff Baseline** | Diffing against latest draft | Diffing against approved baseline v1 | Prevents cumulative draft drift; guarantees contract fidelity. |

---

## 3. Auto-Send Rule & Edge Case Learnings

The **20-consecutive-unchanged auto-send rule** was designed to prevent premature automation:
- **Whitespace Normalization:** Reviewers often added or removed trailing newlines without changing substance. Normalizing whitespace prevents false resets.
- **Fail-Safe Trigger:** Any human edit to a high-risk category (e.g. `refund`, `legal`, `complaint`) immediately locks auto-send and resets the counter to 0.
- **Audit Logging:** Every state transition is recorded in SQLite `auto_send_rules` and `audit_log` with before/after snapshots for full enterprise compliance.
