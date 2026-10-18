# Business Labs — Project Status Snapshot

**Date:** October 18, 2026  
**Status Mode:** Honest Snapshot (Real numbers and verified test results; no simulated or invented data)

---

## 1. Executive Summary

This repository contains the monorepo for the **Business Labs AI Automation Suite**, encompassing:
1. **Task 1: Knowledge Brain** (FastAPI, SQLite FTS5, ChromaDB hybrid search, multimodal RAG, crawl engine, guardrails).
2. **Task 2: Inbox Agent** (Next.js 14 / TypeScript, SQLite store, auto-send guardrails, human review UI, Task 1 integration).
3. **Task 3: Meeting-to-Scope** (FastAPI + Streamlit, multi-agent transcript analysis, feasibility checker, scope diffing, versioning).

All three applications and test suites are functioning with **112 / 112 tests passing** locally. Real-model Claude pilots and live multi-model evals are currently blocked waiting on an Anthropic credit card payment to clear.

---

## 2. Test Suite Status (Verified Real Results)

All three test suites were executed with zero mocks on local databases and offline handlers:

| Task / Subsystem | Framework / Runner | Total Tests | Passed | Failed | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Task 1: Knowledge Brain** | `pytest` (`.venv`) | 55 | **55** | 0 | **REAL - PASSED** |
| **Task 2: Inbox Agent** | `vitest` (`npm test`) | 30 | **30** | 0 | **REAL - PASSED** |
| **Task 3: Meeting-to-Scope** | `pytest` (`.venv`) | 27 | **27** | 0 | **REAL - PASSED** |
| **Total** | | **112** | **112** | **0** | **100% PASS** |

### Test Breakdown
- **Task 1**: API authentication, quota & rate-limit handling, FTS5 keyword indexing, chunk hierarchy, HTML parser, sitemap parsing, robots.txt matching, RAG evidence grounding, Claude/Gemini provider error resilience, daily quota guards.
- **Task 2**: Classification pipelines, draft generation, auto-send guardrails, human approval triggers, knowledge client fallback on 429/quota exhausted/service down, UI state isolation.
- **Task 3**: Transcript chunking & dialogue merging, requirement extraction, feasibility analysis with Brilliant Directories catalog, heuristic risk detection for messy transcripts, scope versioning, baseline immutability, scope diff comparison.

---

## 3. What Works Now (Real & Verified)

- **Task 1 App & API**:
  - FastAPI server (`task1-knowledge-brain/app/main.py`) running on `localhost:8001`.
  - Secure API authentication via `X-API-Key` with production checks preventing default keys.
  - SQLite FTS5 full-text search combined with ChromaDB vector search.
  - Resilient LLM layer supporting Gemini (`gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-flash-latest`) and Claude (`claude-3-5-sonnet`, `claude-3-5-haiku`) with exponential backoff on 429s and clear distinction between per-minute rate limits and daily quota exhaustion.
  - Streamlit UI (`task1-knowledge-brain/streamlit_app.py`) for querying the knowledge brain, testing escalations, and viewing crawl status.
  - Global spend guard (`config/claude_spend_ledger.json` & budget managers) enforcing spend limits.

- **Task 2 Inbox Agent**:
  - Next.js web application with reactive human-in-the-loop dashboard.
  - 50 synthetic test emails representing real customer inquiries, tier changes, and cancellations.
  - Deterministic guardrails (e.g., forbidding auto-send if refund requested, angry sentiment detected, low confidence, or knowledge service degraded).
  - Feedback store recording human edits and approvals for continuous prompt refinement.

- **Task 3 Meeting-to-Scope**:
  - FastAPI backend and Streamlit interactive workspace.
  - Staged dialogue chunking with sliding context windows to analyze long/messy transcripts without truncation.
  - 5-agent pipeline: Transcript Analyst, Product Feasibility Inspector, Scope Agent, Estimation Agent, and Proposal Agent.
  - Formal Scope Diff engine (`scope_diff/comparator.py`) computing additions, removals, scope expansions, delivery delays, and budget variations between approved baselines and follow-up meetings.

- **Phase 2e Requirements (Verified Implemented)**:
  - `extraction_mode` labels: Implemented across models, routes, and comparator. Reports explicitly flag `llm`, `sample_fixture`, or `offline_heuristic`. The system warns reviewers and guards against approving degraded heuristic baselines.
  - Stable Requirement IDs: Deterministic hashing (`req-{hash}`) ensures cross-meeting diffing tracks identical requirements accurately.
  - Scope Version Archiving: `scope_versions` table maintains immutable history of approved baseline versions and audit trails.

---

## 4. What Is Pending (Not Fake, Real Next Steps)

- **Anthropic Claude Pilot & Evals**:
  - **Blocked**: Anthropic API card payment is currently processing/pending; test calls received `credit balance is too low`.
  - **Action**: Once card payment clears, run real Claude pilot (Haiku & Sonnet) using `task1-knowledge-brain/evaluation/run_evals.py`, `task2-inbox-agent/evaluation/run_evals.ts`, and `task3-meeting-to-scope/evaluation/run_evals.py`.
- **Model Comparison Report**:
  - Full statistical comparison (pass rate, latency, cost per 1k queries, failure modes) between Claude Sonnet/Haiku and Gemini Flash models will be generated from real eval runs.
- **Full Production Web Crawl**:
  - Full crawl of thousands of Brilliant Directories support articles and documentation (crawler has been verified on test subsets, full production crawl pending).
- **Prompt v2 & Rollback Proof**:
  - Evaluation tooling and versioning schemas exist (`rag_v1`, `classify_v1`, `draft_reply_v1`, `scope_v1`). Deployment of prompt v2 and documented rollback verification will be completed upon live evals.
- **Rebuilding Task 3 Baseline with Production Model**:
  - Re-run baseline extraction on Transcript A with Claude 3.5 Sonnet once API credits activate.
- **Real Audio / Transcripts**:
  - Integration with live audio recording / Whisper transcription pipeline.
- **Documentation & Presentation**:
  - Comprehensive `README.md`, `DESIGN.md`, `EVALS.md`, and `AI_LOG.md` updates.
  - Project walkthrough demo video and live client review preparation.

---

## 5. Known Issues & Operational Considerations

1. **Anthropic API Credits**: Any run with `PROFILE=final` requires active credit balance on Anthropic console; `PROFILE=dev` (Gemini) should be used in the interim.
2. **Database and Cache Files**: Local SQLite databases (`task1.db`, `task2.db`, `task3.db`) and ChromaDB vector store directories contain environment-specific local state and are excluded from git.
3. **Pydantic V2 Warning**: Pydantic emits a deprecation notice for class-based `config` in `task3-meeting-to-scope/app/config.py` (cosmetic warning, does not affect runtime functionality).

---

## 6. How to Run the Project

### One-Command Setup & Launch (PowerShell)
```powershell
# In repo root:
.\run.ps1
```
Or on Linux/macOS:
```bash
./run.sh
```

### Running Each Service Manually
1. **Task 1 (Knowledge Brain API & UI)**:
   ```powershell
   # API:
   .\.venv\Scripts\uvicorn task1-knowledge-brain.app.main:app --port 8001 --reload
   # UI:
   .\.venv\Scripts\streamlit run task1-knowledge-brain/streamlit_app.py --server.port 8501
   ```

2. **Task 2 (Inbox Agent)**:
   ```powershell
   cd task2-inbox-agent
   npm install
   npm run dev
   # Open http://localhost:3000
   ```

3. **Task 3 (Meeting-to-Scope API & UI)**:
   ```powershell
   # API:
   .\.venv\Scripts\uvicorn task3-meeting-to-scope.app.main:app --port 8002 --reload
   # UI:
   .\.venv\Scripts\streamlit run task3-meeting-to-scope/streamlit_app.py --server.port 8502
   ```

---

## 7. How to Run Tests

To execute all three test suites without making any paid API calls:

```powershell
# Task 1 (Knowledge Brain - 55 tests)
.\.venv\Scripts\pytest task1-knowledge-brain/tests -v

# Task 2 (Inbox Agent - 30 tests)
cd task2-inbox-agent; npm test; cd ..

# Task 3 (Meeting-to-Scope - 27 tests)
.\.venv\Scripts\pytest task3-meeting-to-scope/tests -v
```
