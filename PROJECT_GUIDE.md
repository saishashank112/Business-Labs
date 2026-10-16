# AI Tech Consultant: Complete Project Run & Walkthrough Guide

> **One-Stop Guide** explaining how to run, explore, and demonstrate the three connected applications of the **AI Tech Consultant** system.

---

## 1. Quick Start: How to Run the Project

### Option A: One-Command Startup (Recommended)

#### On Windows (PowerShell):
```powershell
.\run.ps1
```

#### On Linux / macOS (Bash):
```bash
chmod +x run.sh
./run.sh
```

#### Using Docker Compose:
```bash
docker compose up --build
```

---

### Option B: Running Each Service Individually

If you prefer to start each service in separate terminal windows:

| Terminal | Service | Command | Directory |
|---|---|---|---|
| **Terminal 1** | Task 1 Backend API | `..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001` | `task1-knowledge-brain` |
| **Terminal 2** | Task 1 Streamlit UI | `..\.venv\Scripts\streamlit.exe run streamlit_app.py --server.port 8501` | `task1-knowledge-brain` |
| **Terminal 3** | Task 2 Next.js App | `npm run dev -- -p 3000` | `task2-inbox-agent` |
| **Terminal 4** | Task 3 Backend API | `..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8002` | `task3-meeting-to-scope` |
| **Terminal 5** | Task 3 Streamlit UI | `..\.venv\Scripts\streamlit.exe run streamlit_app.py --server.port 8502` | `task3-meeting-to-scope` |

---

## 2. About Each Localhost URL

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ACTIVE LOCALHOST PORTS                           │
├──────────────┬──────────────────┬───────────────────────────────────────────┤
│ URL          │ Service          │ Purpose                                   │
├──────────────┼──────────────────┼───────────────────────────────────────────┤
│ :8001        │ Task 1 API       │ Knowledge Brain REST API (FastAPI)        │
│ :8501        │ Task 1 UI        │ Knowledge Search & HITL Streamlit App     │
│ :3000        │ Task 2 Web       │ Inbox Agent Support Review UI (Next.js)   │
│ :8002        │ Task 3 API       │ Meeting-to-Scope Multi-Agent API (FastAPI)│
│ :8502        │ Task 3 UI        │ Meeting-to-Scope & Diff UI (Streamlit)    │
└──────────────┴──────────────────┴───────────────────────────────────────────┘
```

### 1. Task 1 API — `http://localhost:8001`
- **Swagger Documentation:** [http://localhost:8001/docs](http://localhost:8001/docs)
- **Role:** The central knowledge engine for Brilliant Directories (BD) documentation.
- **Authentication:** Requires `X-API-Key: change-me-in-production` header.
- **Key Endpoints:**
  - `POST /query`: Answers technical questions using hybrid search (ChromaDB + SQLite FTS5) with markdown citations.
  - `POST /ingestion/run`: Triggers the polite crawler on the BD Solution Center sitemap.
  - `GET /ingestion/status`: View crawl status, manifest counts, and re-indexed articles.
  - `GET /escalations`: Lists questions that could not be answered and were escalated to humans.
  - `POST /escalations/{id}/resolve`: Resolves an escalation and stores approved knowledge.
  - `GET /health`: Health check endpoint.

### 2. Task 1 UI — `http://localhost:8501`
- **Role:** Interactive search interface and admin dashboard for Knowledge Brain.
- **What You See:**
  - **Ask Question Tab:** Input box for queries. Returns grounded answers, direct links to BD articles, screenshot previews, and response latency.
  - **Escalation Queue Tab:** Unresolved questions that lack sufficient documentation. Experts can enter approved answers that flow back into search memory.
  - **Ingestion & Manifest Tab:** Shows crawled page counts, database stats, and crawl controls.

### 3. Task 2 Web App — `http://localhost:3000`
- **Role:** Customer support triage dashboard built with Next.js 14 and strict TypeScript.
- **What You See:**
  - **50-Email Inbound Feed:** Real-world customer tickets categorized into 7 types (how-to, troubleshooting, project, refund, complaint, quote, follow-up), including 15 hold-out cases.
  - **Guardrail Badges:** Real-time safety validation (prevents unauthorized refunds, delivery dates, or price commitments).
  - **AI Reply Drafter:** Retrieves citations over HTTP from Task 1 (`:8001`).
  - **Human Review Actions:**
    - `Approve & Send` (Simulated dispatch)
    - `Edit then Send` (Feeds the human learning store)
    - `Reject` / `Mark for Expert`
  - **20-Draft Auto-Send Rule Engine:** Live counter tracking consecutive unchanged sends. High-risk categories (refunds, complaints) are locked by safety policy.

### 4. Task 3 API — `http://localhost:8002`
- **Swagger Documentation:** [http://localhost:8002/docs](http://localhost:8002/docs)
- **Role:** Multi-agent pipeline converting kickoff meeting transcripts into engineering scopes and proposals.
- **Key Endpoints:**
  - `POST /api/transcripts/{id}/analyze`: Runs staged dialogue analysis and extracts requirements.
  - `POST /api/transcripts/{id}/draft-scope`: Checks platform feasibility via Task 1 HTTP API and drafts a 10-section Scope of Work.
  - `POST /api/scopes/{id}/approve`: Gates sending by approving a baseline scope version.
  - `POST /api/scopes/{id}/diff`: Diffs a follow-up transcript against an approved baseline.

### 5. Task 3 UI — `http://localhost:8502`
- **Role:** Technical sales consultant workspace.
- **What You See:**
  - **Transcript Selection:** Choose between Transcript A (Kickoff), Transcript B (Complex), or Transcript C (Follow-Up Revisions).
  - **Requirement Feasibility Grid:** Automatically flags features as `native`, `custom`, or `needs_clarification`.
  - **10-Section SOW & Estimate:** Breakdowns with Low, Likely, and High hours and milestone pricing.
  - **Approval Gate:** Button to lock and approve baseline Scope v1.
  - **Scope Diff Report:** Compares Transcript C against approved baseline v1 (highlighting added items, removed items, timeline shift, and budget delta).

---

## 3. Step-by-Step Project Walkthrough Guide

Follow these steps for a live review, demo, or grading walkthrough:

### Step 1: Explore Task 1 (Knowledge Brain)
1. Open **[http://localhost:8501](http://localhost:8501)** in your browser.
2. In the question box, enter:
   ```text
   How do I configure email forwarders in Brilliant Directories?
   ```
3. Click **Ask Question**.
4. **Observe:**
   - The status is `answered`.
   - The answer explains that email forwarders were removed in June 2024 and lists the recommended alternatives (Google Workspace, Thunderbird, Apple Mail).
   - Verifiable citations point directly to the live BD Solution Center article.
   - Relevant screenshots are displayed.
5. Next, try an out-of-scope / adversarial question:
   ```text
   Can Brilliant Directories compile custom C++ root binaries on the server?
   ```
6. **Observe:**
   - The status is `insufficient_evidence`.
   - The system abstains honestly and escalates the ticket to the **Escalation Queue**.

---

### Step 2: Explore Task 2 (Inbox Agent)
1. Open **[http://localhost:3000](http://localhost:3000)** in your browser.
2. Look at the left sidebar containing the **50 inbound emails**.
3. Click on **`email-01`** (a standard `how-to` question about email forwarders).
   - Click **Run Pipeline (Classify + Draft)**.
   - Notice that the agent queries Task 1 via HTTP, retrieves the article citations, and writes a polite, cited draft.
4. Click on **`email-15`** (a high-risk refund request).
   - **Observe Guardrail Safety:**
     - The risk level is flagged as `high`.
     - The guardrail engine blocks automatic sending (`auto_send_allowed: false`).
     - `needs_human_approval` is set to `true`.
5. Test the **Feedback & Auto-Send Counter:**
   - Make a text edit in the draft box.
   - Click **Edit & Send**.
   - Notice that the consecutive unchanged counter resets to 0 and the human edit is stored in the SQLite audit log.

---

### Step 3: Explore Task 3 (Meeting to Scope & Scope Diff)
1. Open **[http://localhost:8502](http://localhost:8502)** in your browser.
2. **Phase 1: Initial Kickoff (Transcript A)**
   - Select **Transcript A (Initial Kickoff Meeting)** from the dropdown.
   - Click **Run Staged Analysis**.
   - Review the extracted requirements and feasibility classifications (Stripe, categories, SSL).
   - Click **Generate Scope & Estimate**.
   - Review the 10-section SOW, the hours estimation (e.g., 40h), and the executive proposal.
   - Click **Approve Baseline Scope (v1)**. *(This locks the contract baseline)*.
3. **Phase 2: Follow-Up Scope Revisions (Transcript C)**
   - Select **Transcript C (Follow-Up Meeting with Changes)** from the dropdown.
   - Notice that Transcript C explicitly adds Twilio SMS 2FA, removes the mass email newsletter setup, and pushes delivery from Nov 15 to Dec 5.
   - Click **Compare Against Approved Baseline v1**.
4. **Observe the Scope Diff Report:**
   - **Added:** `req-c-1: Twilio SMS 2FA integration`
   - **Removed:** `req-3: Mass email campaign setup (Client requested removal)`
   - **Timeline Shift:** Moved from `2026-11-15` to `2026-12-05` (+20 days)
   - **Net Effort & Cost Delta:** Automatically recalculated without manual spreadsheet editing.

---

## 4. How to Run Tests and Evaluations

To verify code correctness and benchmark results:

```bash
# 1. Task 1 Unit Tests (31 passed in ~1.2s)
cd task1-knowledge-brain
pytest tests/

# 2. Task 1 Evaluation Suite (20 cases: 10 typical, 5 edge, 5 adversarial)
python evaluation/run_evals.py

# 3. Task 2 Unit Tests (12 passed in ~0.8s)
cd ../task2-inbox-agent
npm test

# 4. Task 2 Evaluation Suite (50 emails including 15 holdouts)
npx tsx evaluation/run_evals.ts

# 5. Task 3 Unit Tests (8 passed)
cd ../task3-meeting-to-scope
pytest tests/

# 6. Task 3 Evaluation Suite (20 cases: feasibility, diffs, proposals)
python evaluation/run_evals.py
```

---

## 5. Architectural Compliance Checklist

- [x] **Strict HTTP Decoupling:** Task 2 and Task 3 call Task 1 exclusively via `POST /query` with `X-API-Key`.
- [x] **Zero Code Sharing:** No shared imports across apps.
- [x] **Zero Database Sharing:** Isolated databases (`task1.db`, `task2.db`, `task3.db`).
- [x] **Multimodal Ingestion:** Screenshots parsed, described, and cited.
- [x] **Guardrails:** Zero unauthorized promises of refunds or pricing.
- [x] **Baseline Scope Diff:** Follow-ups compare strictly against approved baselines.
