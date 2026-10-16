# Knowledge Brain API Documentation

The **Knowledge Brain** is an AI-powered technical consultation service for the Brilliant Directories platform. It features an automated polite crawler, heading-based chunker, hybrid search (ChromaDB vector embeddings + SQLite FTS5 keyword BM25), evidence-grounded RAG with inline citations, screenshot description caching, and a human-in-the-loop escalation loop.

---

## Base URL & Authentication

- **Base URL:** `http://localhost:8001`
- **Required Header for all endpoints (except `/health`):**
  ```http
  X-API-Key: change-me-in-production
  ```
- **Optional Request Tracing Header:**
  ```http
  X-Request-Id: <uuid>
  ```
  *(If omitted, the server automatically generates and returns a unique `X-Request-Id` in the response headers.)*

---

## Endpoints

### 1. Health Check

Verifies server liveness, database connectivity, configured LLM model availability, and uptime.

- **Method:** `GET`
- **Path:** `/health`
- **Auth:** None

#### Example Request
```bash
curl -X GET http://localhost:8001/health
```

#### Example Response (200 OK)
```json
{
  "status": "ok",
  "db": "connected",
  "model": "gemini-2.5-flash",
  "model_status": "available",
  "fallback_model": "gemini-flash-latest",
  "uptime_seconds": 3600.5
}
```

---

### 2. Query Knowledge Base

Answers a user query using hybrid retrieval and RAG. Enforces strict evidence grounding, inline markdown citations, and automatic escalation when documentation is insufficient or when model errors occur.

- **Method:** `POST`
- **Path:** `/query`
- **Auth:** `X-API-Key: <key>`

#### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `question` | string | Yes | The technical question to answer (1–2000 chars). |
| `context` | string | No | Optional additional caller context. |
| `mode` | string | No | Retrieval mode: `hybrid` (default), `vector`, or `keyword`. |

#### Response Schema
| Field | Type | Description |
|---|---|---|
| `answer` | string | Grounded markdown answer or error explanation. |
| `status` | string | `answered`, `insufficient_evidence`, or `error`. |
| `error_code` | string \| null | Standard error code when `status="error"`: `QUOTA_EXHAUSTED`, `RATE_LIMITED`, `LLM_UNAVAILABLE`, `TIMEOUT`, `INVALID_OUTPUT`, `INTERNAL_ERROR`. |
| `sources` | array | List of cited documentation sources (`title`, `url`, `relevance`). |
| `images` | array | List of image references. |
| `needs_human` | boolean | Flag indicating human review is needed (true on error and insufficient_evidence). |
| `escalation_id` | string \| null | UUID of human escalation record in database (only created for `insufficient_evidence`; null for infrastructure errors). |
| `request_id` | string | Tracing request ID (all errors are logged with this request ID). |

#### Example Response: Success (200 OK, answered)
```json
{
  "answer": "Brilliant Directories includes an internal email marketing tool designed for newsletters and member updates. However, for massive email campaigns exceeding server delivery limits, the platform recommends integrating third-party email services such as Mailchimp or SendGrid. See [Can I Send A Mass Email Campaign Using Brilliant Directories?](https://support.brilliantdirectories.com/support/solutions/articles/5000558357-can-i-send-a-mass-email-campaign-using-brilliant-directories-).",
  "status": "answered",
  "error_code": null,
  "sources": [
    {
      "title": "Can I Send A Mass Email Campaign Using Brilliant Directories?",
      "url": "https://support.brilliantdirectories.com/support/solutions/articles/5000558357-can-i-send-a-mass-email-campaign-using-brilliant-directories-",
      "relevance": 0.942
    }
  ],
  "images": [],
  "needs_human": false,
  "escalation_id": null,
  "request_id": "8a7d18bc-1ef2-48a0-97ec-0322cbbbb8fa"
}
```

#### Example Response: Error / Downstream Failure (200 OK, error)
> Infrastructure errors are logged with `request_id` but do NOT create escalation tickets.
```json
{
  "answer": "Knowledge service error: Configured model returned 404 NOT_FOUND",
  "status": "error",
  "error_code": "LLM_UNAVAILABLE",
  "sources": [],
  "images": [],
  "needs_human": true,
  "escalation_id": null,
  "request_id": "9c1182ef-6644-42b3-96b6-eef904baef87"
}
```

---

### 3. Run Ingestion Crawler

Triggers an asynchronous polite crawl and indexing job. Reads robots.txt, respects rate limits, updates SQLite crawl manifest, chunks new/updated articles, and syncs vector/keyword stores.

- **Method:** `POST`
- **Path:** `/ingestion/run`
- **Auth:** `X-API-Key: <key>`

#### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `max_pages` | integer | No | Maximum number of articles to crawl (default from config). |

#### Example Request
```bash
curl -X POST http://localhost:8001/ingestion/run \
  -H "X-API-Key: change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 10}'
```

#### Example Response (202 Accepted)
```json
{
  "job_id": "d043bbf6-b5ca-4a7b-b384-1845faec4527",
  "status": "started",
  "message": "Ingestion started"
}
```

---

### 4. Check Ingestion Status

Returns the current state and report counts from the crawler.

- **Method:** `GET`
- **Path:** `/ingestion/status`
- **Auth:** `X-API-Key: <key>`

#### Example Request
```bash
curl -X GET http://localhost:8001/ingestion/status \
  -H "X-API-Key: change-me-in-production"
```

#### Example Response (200 OK)
```json
{
  "status": "completed",
  "last_run": "2026-10-16T11:24:00Z",
  "report": {
    "added": 5,
    "updated": 0,
    "removed": 0,
    "failed": 0,
    "unchanged": 0
  }
}
```

---

### 5. List Escalations

Retrieves escalations created automatically when documentation context is insufficient or when questions are manually flagged.

- **Method:** `GET`
- **Path:** `/escalations?status=open`
- **Auth:** `X-API-Key: <key>`

#### Example Request
```bash
curl -X GET "http://localhost:8001/escalations?status=open" \
  -H "X-API-Key: change-me-in-production"
```

#### Example Response (200 OK)
```json
[
  {
    "id": "e7c10b7b-f48e-4a69-80fb-1cb1135f3b79",
    "question": "How do I configure webhook signatures for custom third-party ERP?",
    "evidence": "No matching articles found in documentation.",
    "reason": "Documentation context did not contain enough details to fully answer the question.",
    "status": "open",
    "created_at": "2026-10-16T10:45:00Z",
    "resolved_at": null,
    "resolver": null
  }
]
```

---

### 6. Resolve Escalation & Ingest Expert Knowledge

Allows a human consultant or subject-matter expert to answer an open escalation. The answer is stored in `expert_knowledge` and indexed immediately so future matching queries are answered instantly.

- **Method:** `POST`
- **Path:** `/escalations/{id}/resolve`
- **Auth:** `X-API-Key: <key>`

#### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `answer` | string | Yes | The verified, authoritative answer. |
| `reviewer` | string | Yes | Name or identifier of the expert reviewer. |
| `expires_at` | string | No | Optional ISO 8601 expiry timestamp. |

#### Example Request
```bash
curl -X POST http://localhost:8001/escalations/e7c10b7b-f48e-4a69-80fb-1cb1135f3b79/resolve \
  -H "X-API-Key: change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{
    "answer": "To configure webhook signatures, navigate to Developer Tools > Webhooks in Brilliant Directories, copy the Webhook Signing Secret, and verify HMAC SHA256 signatures in your receiving endpoint.",
    "reviewer": "Jane Doe, Senior BD Architect"
  }'
```

#### Example Response (200 OK)
```json
{
  "id": "e7c10b7b-f48e-4a69-80fb-1cb1135f3b79",
  "status": "resolved",
  "knowledge_id": "ek-a8b29c11"
}
```
