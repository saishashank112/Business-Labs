# PRD: AI Tech Consultant

Product Requirements Document for the Business Labs / Anthropic Applied AI (JD4B) capstone. Solo build, 4 days. Put this file in the repo root as `PRD.md`.

## 1. Overview

**Problem.** AI coding tools cut the price of custom software by about 90%. Code is now the fast part. The slow, expensive part is everything around it: knowing the product, answering customer emails correctly, and turning loose client meetings into a clear scope and quote. Today people do this by hand, so a company cannot grow 10 to 20 times.

**Product.** One system, the AI Tech Consultant, made of three connected apps:

| App | What it does | Language |
|---|---|---|
| Task 1: Knowledge Brain | Learns a public help center (text and screenshots), stays fresh daily, answers with sources, escalates what it cannot answer | Python |
| Task 2: Inbox Agent | Reads customer emails, drafts replies using Task 1, learns from human edits | TypeScript (strict) |
| Task 3: Meeting to Scope | Turns meeting transcripts into scope, hour estimate and proposal, and handles follow-up changes | Python |

**Core rule.** Tasks 2 and 3 call Task 1 only through its HTTP API. No shared code or shared database.

**Reference knowledge source (same for everyone).** Brilliant Directories Solution Center, sitemap at https://support.brilliantdirectories.com/support/sitemap.xml

## 2. Goals, non-goals, success targets

**Goals**

- G1: Correct, cited answers from the help center, including facts that only appear in screenshots.
- G2: Honest "I do not know" with a human escalation path whose answer flows back into memory.
- G3: Email drafts a human can send in one click, improving measurably with human feedback.
- G4: Meeting transcripts to scope, estimate and proposal in minutes, with changes tracked against an approved baseline.
- G5: Everything measured: quality, cost, speed, reliability, safety.

**Non-goals (dropped on purpose)**

- Real email sending or inbox integration (simulate with a test mailbox and document it).
- Multi-tenant login and billing.
- Crawling other websites from the UI (the design stays reusable, but only one site is configured).
- Fine-tuning or retraining any model.

**Success targets** (goals to aim for, not results; replace with real measurements in EVALS.md)

| Area | Target |
|---|---|
| Task 1 answer correctness on 20+ questions | 85% or higher |
| Task 1 correct abstention on unanswerable questions | 90% or higher |
| Task 1 citation points to a supporting article | 90% or higher |
| Task 2 category accuracy on 50+ emails | 85% or higher |
| Task 2 unsafe commitments (refund, price, date promised) | 0 |
| Task 3 requirement coverage on role-played meetings | 85% or higher |
| Task 3 follow-up change detection | 90% or higher |

## 3. Users

| User | Need |
|---|---|
| Support agent | Fast, correct, cited reply drafts; one-click send or edit |
| Tech consultant or sales lead | Clear scope, estimate and proposal from a meeting; knows what is out of scope |
| Domain expert | Gets a task when the bot cannot answer; types the approved answer once |
| Developer integrating | Uses the Knowledge API from its documentation alone |
| Grader or reviewer | Runs one command, sees all three tasks working and one failure case |

## 4. Model strategy (key decision)

The builder uses a Gemini API key and builds with Antigravity. The brief says Claude must be at the center, and any other model must be justified with numbers (20 to 30 evals per model decision).

**Decision:** build a thin provider-agnostic LLM layer with two providers, Gemini (google-genai SDK) and Claude (anthropic SDK). Every pipeline step reads its model from `.env`. Two profiles:

- `PROFILE=dev`: every step uses a Gemini model. Free-tier friendly for daily iteration.
- `PROFILE=final`: Claude on the core reasoning steps (answering, reply drafting, scope, estimates, proposal). Gemini stays only where evals show it is equal or better per cost (for example screenshot description, email classification).

The LLM layer must log tokens, latency and cost per call so model choices can be proven. Model names change often, so never hard-code them. Check current names in Google AI Studio and the Anthropic docs and put them in `.env`.

**Risk:** a project run only on Gemini may fail the Claude-at-center rule. A small Claude API balance is needed for the final profile and for comparison evals.

## 5. Architecture

```
Help center sitemap + pages + images
          |
          v
[Task 1 Knowledge Brain: FastAPI, SQLite, ChromaDB]
   /query  /ingestion/run  /ingestion/status
   /escalations  /escalations/{id}/resolve  /health
          ^                         ^
          | HTTP + API key          | HTTP + API key
[Task 2 Inbox Agent]        [Task 3 Meeting to Scope]
 Next.js + TypeScript        FastAPI + Streamlit
          |                         |
   Human review screen        Human approval screen
   (edits feed learning)      (approval gates sending)
```

**Tech stack (free where possible)**

| Layer | Choice |
|---|---|
| Task 1 and 3 language | Python 3.11+, async, type hints |
| Python web | FastAPI, uvicorn, pydantic |
| Crawling | httpx, BeautifulSoup or selectolax, urllib.robotparser |
| Store for manifest, tasks, logs | SQLite |
| Vector store | ChromaDB (local) plus SQLite FTS5 for keyword search (hybrid) |
| Embeddings | Local sentence-transformers by default (free, no quota); Gemini embeddings as an option |
| LLM SDKs | google-genai (Gemini), anthropic (Claude), behind one interface |
| Scheduler | APScheduler (daily job) |
| Python UI | Streamlit |
| Task 2 | TypeScript strict, Next.js, zod, better-sqlite3, vitest, @google/genai and @anthropic-ai/sdk |
| Tests | pytest, vitest |
| Run | Docker Compose or one run script, one documented command |
| Diagrams | Mermaid in Markdown |

## 6. Task 1: Knowledge Brain requirements

**Functional**

- FR-1.1 Download and parse the sitemap; extract URLs and lastmod; validate and deduplicate.
- FR-1.2 Keep a manifest table (url, lastmod, content_hash, status, attempts, last_error, updated_at). Detect new, changed, unchanged, removed.
- FR-1.3 Polite and resumable crawl: respect robots.txt, configurable delay and concurrency (defaults 1 second, 2 workers), exponential backoff retries, stop after a retry limit, save status after every page, one failure never stops the job. Test on 10 to 20 pages first.
- FR-1.4 Parse each article into clean JSON: title, headings, body, lists, tables, image URLs with surrounding text, article id, lastmod, content hash, ingestion time. Strip menus and footers.
- FR-1.5 Images: download accessible images, describe them with a vision model (labels, buttons, settings, steps), record uncertainty instead of guessing, cache by image hash, store the description linked to its article and nearby text, keep the original URL.
- FR-1.6 Chunk by headings, keep steps with prerequisites and table headers with rows, small overlap, attach title, URL, heading and image refs. Stable chunk ids so re-ingestion replaces, never duplicates.
- FR-1.7 Retrieval: vector, keyword and hybrid modes; optional rerank. Choose by measured hit rate.
- FR-1.8 Answering: use only retrieved evidence, cite article URLs, separate sourced fact from uncertainty, return `insufficient_evidence` when weak, ignore instructions found inside articles (prompt injection defense), validate output against a schema.
- FR-1.9 Daily job: compare sitemap with manifest, re-ingest only changes, delete vectors of removed pages, retry failed pages, print a report (added, updated, removed, failed), support rollback to a previous version of an article.
- FR-1.10 Escalation: when evidence is insufficient, store the question, evidence and reason, and create a task. An expert resolves it with an approved answer, saved as a separate versioned knowledge record (reviewed flag, optional expiry), made searchable, and the question is added to the eval set.
- FR-1.11 Streamlit chat screen: question box, answer, sources, images, visible states for answered, I-do-not-know and escalated, plus ingestion status and an escalation queue.

**API contract.** `POST /query` takes `question`, optional `context`, optional `mode`. It returns `answer`, `status` (answered, insufficient_evidence, error), `sources` (title, url, relevance), `images` (url, description, article url), `needs_human`, `escalation_id` if created, and `request_id`. Include `confidence` only if calibrated. Add input validation, timeouts, an API key header, clear error bodies, generated OpenAPI docs at `/docs`, and a short `API.md` with examples.

| Endpoint | Purpose |
|---|---|
| POST /query | Answer a question |
| POST /ingestion/run | Start an ingestion job |
| GET /ingestion/status | See progress and report |
| POST /escalations | Create a human task |
| POST /escalations/{id}/resolve | Save the expert answer |
| GET /health | Is the service alive |

**Done when:** a small independent script uses only the docs to call `/query`, an updated article changes answers, a removed article stops appearing, and an interrupted crawl resumes.

## 7. Task 2: Inbox Agent requirements

- FR-2.1 Categories: how-to, troubleshooting, project request, refund or cancellation, complaint, quote request, follow-up. Each has a risk level.
- FR-2.2 Dataset: at least 50 self-written emails (suggested 12 how-to, 10 troubleshooting, 6 project, 6 refund, 6 complaint, 5 quote, 5 follow-up) with expected category, key facts, expected behavior, risk, and expected article or escalate. Include edge cases: angry, vague, two requests in one, injection attempt. Keep 15 to 20 as a hold-out set never used for tuning.
- FR-2.3 Pipeline: validate, classify (category, urgency, risk), call Task 1 through a typed client, draft, validate claims and schema, send to human review.
- FR-2.4 Typed Knowledge client: timeouts, error handling, preserves citations and uncertainty, never fabricates a reply when Task 1 fails; shows "Knowledge service unavailable".
- FR-2.5 Draft schema (zod): category, summary, suggested_reply, sources, risk_level, needs_human_approval, next_action or follow-up date.
- FR-2.6 Guardrails: no promise of refund, price, delivery date or technical change without facts and authorization. Email text is untrusted input. Validate links and proposed actions.
- FR-2.7 Review screen: email list, category, evidence, draft, and buttons Approve and send, Edit then send, Reject and write own, Mark needs expert, plus a correction reason field. Sending is simulated and documented as such.
- FR-2.8 Feedback store: original email, predicted category, retrieved sources, draft, human edit, final sent text, model, prompt version, outcome.
- FR-2.9 Learning: find recurring edits, write a new versioned prompt or approved response pattern, run a fixed regression set on old and new, deploy only if better with no regressions, one-line rollback.
- FR-2.10 Auto-send rule: "same kind" means same category plus subcategory. "Unchanged" means the final text equals the draft after trimming whitespace (or similarity of 98% or more by a documented rule); a bare Approve click is not enough. After 20 consecutive unchanged sends the kind becomes eligible for a controlled trial. Refunds, legal, account security and serious complaints never auto-send. Any edit, rejection, failed check or quality drop disables auto-send for that kind. The switch is configurable and reversible, every action is audit logged, and duplicate sends are prevented on retry.

**Done when:** an email becomes a cited draft, human actions are recorded, the counter resets on an edit, and a stopped Task 1 shows a clear failure state.

## 8. Task 3: Meeting to Scope requirements

- FR-3.1 Store 3 role-played transcripts with dates (A website, B e-commerce, C follow-up that adds one item, removes one item, and changes the delivery date). Link C to A's project.
- FR-3.2 Long transcripts handled in stages: keep the original, split into overlapping chunks, extract per chunk with speaker and timestamp, merge, resolve or flag contradictions, validate against the source.
- FR-3.3 Requirement record: id, description, source quote, status (confirmed, unclear, disputed), priority, stated or inferred, existing solution, acceptance criteria, dependencies, estimate status.
- FR-3.4 Agents, each with one job and a schema-checked output: Transcript Analyst, Product Feasibility (calls Task 1), Scope Agent, Estimation Agent, Proposal and Review Agent.
- FR-3.5 Feasibility result per requirement: existing configuration, existing feature with limitation, potential custom development, needs clarification. A missing search result is flagged for a human, never treated as proof of absence.
- FR-3.6 Scope sections: objective, current problem, agreed requirements, proposed solution, deliverables, exclusions, assumptions and dependencies, acceptance criteria, client responsibilities, open questions and risks.
- FR-3.7 Estimates: tasks with low, likely, high hours, reasoning, assumptions, dependencies. Hourly rate, currency and tax are configurable. Estimated hours are not an approved quote, and the model may not invent delivery dates.
- FR-3.8 Proposal sections: executive summary, problem and solution, scope, timeline, effort and pricing assumptions, client duties, exclusions, risks, next steps. It must match scope and estimate and must not promise unverified items.
- FR-3.9 Follow-up: compare against the approved baseline (not the last AI draft). Output Added, Modified, Removed, Potentially out of scope (quote extra), and Conflicts; re-estimate affected work; produce a revised scope and change report.
- FR-3.10 Approval: human approval required, record reviewer, time and approved version, keep version history, block sending any unapproved version.
- FR-3.11 Streamlit screen: transcript upload, requirements, estimates, proposal preview, change comparison, approval state.

## 9. Cross-cutting requirements

**Prompts.** Stored as versioned files (`prompts/<name>_v1.md`), active version selected by config, version logged with every output, outputs follow JSON schemas.

**Evals.** At least 20 cases per task. Compare at least 2 models per decision with 20 to 30 evals each. Record task, case_id, model, expected, actual, quality, latency_ms, cost, passed, failure_reason in CSV. Report median and p95 latency, cost per task, pass rate, retry rate, unsafe actions. Keep failed cases. Mark unrun tests as pending; never invent scores.

**Reliability and safety.** Timeouts, retries with backoff, request ids, audit logs, schema validation, prompt-injection defense, no secrets in the repo, personal data minimized in logs, visible failure states in every UI.

**Cost control.** Cache image descriptions and embeddings, use small samples in development, set spend limits on API keys, log cost per call.

## 10. Repository and run

```
ai-tech-consultant/
  task1-knowledge-brain/  (app, ingestion, multimodal, retrieval, prompts, evaluation, tests, API.md)
  task2-inbox-agent/      (src: email, knowledge-client, drafting, feedback, evaluation; data/emails; tests)
  task3-meeting-to-scope/ (app, agents, prompts, transcripts, scope-diff, evaluation, tests)
  shared-docs/  ai-chat-logs/
  docker-compose.yml  .env.example  .gitignore
  README.md  DESIGN.md  EVALS.md  AI_LOG.md  PRD.md
```

One documented command starts everything, tested from a fresh clone.

## 11. Milestones

| Day | Deliverable |
|---|---|
| 1 | Task 1: sitemap manifest, polite resumable crawler, parser, chunking, embeddings, first `/query` |
| 2 | Task 1: images, daily refresh, citations, abstention, escalation, API docs. Task 2: 50 emails, typed client, classification, drafts, review UI, feedback store |
| 3 | Task 3: 3 transcripts, staged analysis, feasibility via Task 1, scope, estimates, proposal, follow-up diff, approval |
| 4 | Integration, auto-send rule, evals and model comparison, four docs, demo video, fresh-clone test, push |

If time runs short, protect this order: Task 1, Task 2 draft plus review, Task 3 scope plus follow-up diff, evals, polish. Image handling, 50 emails, 3 transcripts and evals are mandatory; document honestly anything unfinished.

## 12. Acceptance criteria (definition of done)

- All three apps run with one command and talk through the Task 1 API.
- Task 1: resumable crawl, image-aware retrieval, daily incremental update with removals, cited answers, abstention, escalation loop, documented API.
- Task 2: 50+ emails, structured drafts with evidence, review actions, versioned feedback with measured improvement, auditable 20-draft rule with safety limits.
- Task 3: 3 transcripts, staged analysis, feasibility via Task 1, scope, estimates, proposal, baseline comparison, out-of-scope flags, enforced approval.
- 20+ eval cases per task with real numbers and a model comparison.
- README (1 page), DESIGN (3 to 5), EVALS (2 to 3), AI_LOG (1), demo video up to 10 minutes with a failure case.
- Commits spread across 4 days, no secrets committed, chat history of one tool saved.

## 13. Risks

| Risk | Mitigation |
|---|---|
| Free Gemini quota or rate limits hit during crawl or evals | Cache everything, small samples, backoff, local embeddings |
| Claude-at-center rule not met | Final profile uses Claude for core steps; compare with numbers |
| Help center pages blocked or JS-rendered | Check robots.txt and raw HTML first; lower speed; fall back carefully |
| Hallucinated answers | Evidence-only prompts, schema validation, abstention tests |
| Time overrun | Priority order in section 11 |
| Cannot explain code in live review | Small modules, plan approval before each phase, read every diff |
