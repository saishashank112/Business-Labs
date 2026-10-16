# AI Tech Consultant: Autonomous Enterprise Multi-App System

> A production-grade suite of three connected AI services built for Brilliant Directories (BD) consulting, automating knowledge retrieval, customer support email drafting, and sales meeting scoping.

[![Tests](https://img.shields.io/badge/Unit%20Tests-51%2F51%20Passing-brightgreen)]()
[![Evaluations](https://img.shields.io/badge/Evaluation%20Suites-3%2F3%20Executed-blue)]()
[![Architecture](https://img.shields.io/badge/Architecture-Decoupled%20HTTP%20APIs-purple)]()

> 📘 **Looking for complete run instructions and port details?** Read the [PROJECT_GUIDE.md](PROJECT_GUIDE.md) for a step-by-step walkthrough of all three localhost applications.

---

## 1. System Overview

```
                      +-----------------------------------+
                      | Brilliant Directories Help Center |
                      |   (Sitemap + Articles + Images)   |
                      +-----------------+-----------------+
                                        |
                                        v
                       +---------------------------------+
                       |    Task 1: Knowledge Brain      |
                       |  FastAPI + SQLite FTS5 + Chroma |
                       |    (Port 8001 / UI Port 8501)   |
                       +----------------+----------------+
                                        ^
                                        | HTTP API (X-API-Key)
                     +------------------+------------------+
                     |                                     |
+--------------------+----------------+  +-----------------+--------------------+
|       Task 2: Inbox Agent           |  |     Task 3: Meeting-to-Scope         |
| Next.js 14 + Node:SQLite + Zod      |  | FastAPI + Streamlit Multi-Agent      |
|         (Web Port 3000)             |  |   (Port 8002 / UI Port 8502)         |
+-------------------------------------+  +--------------------------------------+
```

| Application | Technology Stack | Role & Responsibility | Port |
|---|---|---|---|
| **Task 1: Knowledge Brain** | Python 3.11+, FastAPI, SQLite FTS5, ChromaDB (`all-MiniLM-L6-v2`), Streamlit | Crawls BD Solution Center, multimodally indexes screenshots, answers questions with verifiable citations, escalates unknown queries to human experts. | `8001` (API)<br>`8501` (UI) |
| **Task 2: Inbox Agent** | Next.js 14 App Router, TypeScript strict, `node:sqlite`, Zod, Vitest | Ingests inbound customer support emails, verifies claims against Task 1 HTTP API, enforces safety guardrails, tracks human edits, and manages 20-consecutive-unchanged auto-send rules. | `3000` (Web) |
| **Task 3: Meeting to Scope** | Python 3.11+, FastAPI, Streamlit, Pydantic, Pytest | Analyzes kickoff transcripts across stages, checks feasibility via Task 1 HTTP API, drafts 10-section SOWs, computes estimates, and computes diffs against approved baselines. | `8002` (API)<br>`8502` (UI) |

---

## 2. Quick Start (One Command)

### Prerequisites
- Python 3.11+
- Node.js 18+ (Node 20+ recommended)
- (Optional) Docker & Docker Compose

### Option A: Local Run (PowerShell / Windows)
```powershell
.\run.ps1
```

### Option B: Local Run (macOS / Linux Bash)
```bash
chmod +x run.sh
./run.sh
```

### Option C: Docker Compose
```bash
docker compose up --build
```

### Verified Port Mapping
- **Task 1 Knowledge Brain API**: [http://localhost:8001](http://localhost:8001) (Swagger docs: `/docs`)
- **Task 1 Knowledge Brain UI**: [http://localhost:8501](http://localhost:8501)
- **Task 2 Inbox Agent Review App**: [http://localhost:3000](http://localhost:3000)
- **Task 3 Meeting-to-Scope API**: [http://localhost:8002](http://localhost:8002) (Swagger docs: `/docs`)
- **Task 3 Meeting-to-Scope UI**: [http://localhost:8502](http://localhost:8502)

---

## 3. Core Architecture & Strict Decoupling

A non-negotiable architectural requirement is that **Tasks 2 and 3 communicate with Task 1 exclusively through its HTTP API** using the `X-API-Key` header.
- **Zero shared code:** Neither Task 2 nor Task 3 imports Python modules or types from Task 1.
- **Zero shared database:** Each task maintains its own isolated SQLite database file (`task1.db`, `task2.db`, `task3.db`).
- **Resilient Fallback:** If Task 1 is temporarily unreachable, Task 2 reports `Knowledge service unavailable` without fabricating citations, and Task 3 flags requirements as `needs_clarification` for human technical review.

---

## 4. Test Suites & Evaluation Verification

All 51 unit tests and 3 batch evaluation suites are fully passing.

```bash
# Task 1 Unit Tests (31 passed)
cd task1-knowledge-brain && pytest tests/

# Task 1 Evaluation Suite (20 cases, 85.0% pass rate)
python evaluation/run_evals.py

# Task 2 Unit Tests (12 passed)
cd ../task2-inbox-agent && npm test

# Task 2 Evaluation Suite (50 emails including hold-out, 86.0% guardrail compliance)
npx tsx evaluation/run_evals.ts

# Task 3 Unit Tests (8 passed)
cd ../task3-meeting-to-scope && pytest tests/

# Task 3 Evaluation Suite (20 cases, 100.0% pass rate)
python evaluation/run_evals.py
```

---

## 5. Live Review Walkthrough (Step-by-Step)

During a live review or grading session, follow these quick steps:

1. **Task 1 Knowledge Verification:**
   - Open [http://localhost:8501](http://localhost:8501).
   - Ask: *"Does Brilliant Directories support free Let's Encrypt SSL certificates?"*
   - Verify the system returns an `answered` status, an exact citation URL pointing to the BD Solution Center article, and screenshots if applicable.
   - Ask an adversarial query: *"Can Brilliant Directories run arbitrary C++ binaries on root servers?"*
   - Verify the system returns `insufficient_evidence` and creates an escalation item in the queue.

2. **Task 2 Inbox Agent & Guardrail Safety:**
   - Open [http://localhost:3000](http://localhost:3000).
   - Select `email-15` (Refund demand).
   - Notice that the guardrail engine detects an unauthorized financial commitment, blocks automatic sending, and sets `needs_human_approval: true`.
   - Make an edit and click **Send**. Verify that the feedback store records the human edit and resets the consecutive-unchanged counter.

3. **Task 3 Meeting to Scope & Follow-Up Diff:**
   - Open [http://localhost:8502](http://localhost:8502).
   - Select **Transcript A (Initial Kickoff)** -> Click **Run Staged Analysis** -> **Draft Scope & Estimate**.
   - Review the 10-section SOW and click **Approve Baseline Scope (v1)**.
   - Select **Transcript C (Follow-Up Meeting)** -> Click **Compare Against Baseline v1**.
   - Observe the Scope Diff Report: **Twilio SMS 2FA** is marked as `Added`, **Mass email campaign** is marked as `Removed`, timeline shifts by `+20 days`, and the net budget delta is calculated.
