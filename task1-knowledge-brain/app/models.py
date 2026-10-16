"""Pydantic models for API requests, responses, and internal data."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# ── Ingestion ───────────────────────────────────────────────

class IngestionRequest(BaseModel):
    """Body for POST /ingestion/run."""
    max_pages: Optional[int] = Field(
        default=None,
        description="Override max pages to crawl (None = use config default)",
    )


class IngestionReport(BaseModel):
    """Counts from the last ingestion run."""
    added: int = 0
    updated: int = 0
    removed: int = 0
    failed: int = 0
    unchanged: int = 0


class IngestionStatus(BaseModel):
    """Response for GET /ingestion/status."""
    status: str = "idle"          # idle | running | completed | failed
    last_run: Optional[str] = None
    report: Optional[IngestionReport] = None


class IngestionStarted(BaseModel):
    """Response for POST /ingestion/run."""
    job_id: str
    status: str = "started"
    message: str = "Ingestion started"


# ── Query (placeholder — built fully in Phase 2) ───────────

class QueryRequest(BaseModel):
    """Body for POST /query."""
    question: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = None
    mode: str = Field(default="hybrid", pattern="^(vector|keyword|hybrid)$")


class Source(BaseModel):
    """One cited source in a query response."""
    title: str
    url: str
    relevance: Optional[float] = None


class ImageRef(BaseModel):
    """An image referenced in a query response."""
    url: str
    description: str
    article_url: str


class RAGAnswerOutput(BaseModel):
    """Structured response schema returned by the RAG generation model."""
    sufficient_evidence: bool = Field(
        ...,
        description="True if the documentation context contains sufficient evidence to answer the query; False if documentation is absent, incomplete, or unrelated.",
    )
    answer: str = Field(
        ...,
        description="Evidence-grounded answer with inline markdown citations [Title](URL), or a polite explanation of what documentation is missing when sufficient_evidence is False.",
    )


class QueryResponse(BaseModel):
    """Response for POST /query."""
    answer: str = Field(..., description="Answer grounded strictly in documentation or error explanation.")
    status: str = Field(..., pattern="^(answered|insufficient_evidence|error)$", description="Query status: answered, insufficient_evidence, or error.")
    error_code: Optional[str] = Field(
        default=None,
        pattern="^(QUOTA_EXHAUSTED|RATE_LIMITED|LLM_UNAVAILABLE|TIMEOUT|INVALID_OUTPUT|INTERNAL_ERROR)$",
        description="Standard error code when status is error: QUOTA_EXHAUSTED, RATE_LIMITED, LLM_UNAVAILABLE, TIMEOUT, INVALID_OUTPUT, INTERNAL_ERROR.",
    )
    sources: list[Source] = Field(default=[], description="Cited documentation sources.")
    images: list[ImageRef] = Field(default=[], description="Cited screenshots or diagrams.")
    needs_human: bool = Field(default=False, description="Flag indicating human technical review is required (true on error and insufficient_evidence).")
    escalation_id: Optional[str] = Field(default=None, description="UUID of escalation ticket created if human review is needed (only on insufficient_evidence).")
    request_id: str = Field(..., description="Unique request tracing ID.")


# ── Health ──────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response for GET /health."""
    status: str = "ok"            # ok | degraded | error
    db: str = "connected"
    model: str = "gemini-2.5-flash"
    model_status: str = "available"  # available | unavailable | unchecked
    fallback_model: Optional[str] = None
    claude_status: Optional[dict] = None
    uptime_seconds: float = 0.0


# ── Internal data structures ───────────────────────────────

class SitemapEntry(BaseModel):
    """One URL from the sitemap XML."""
    url: str
    lastmod: Optional[str] = None


class ParsedArticle(BaseModel):
    """Clean structured data extracted from one help-center page."""
    id: str                        # numeric ID from URL
    url: str
    title: str
    headings: list[str] = []
    body: str                      # plain-text body
    lists: list[list[str]] = []    # each list is a list of items
    tables: list[dict] = []        # each table as {headers, rows}
    images: list[dict] = []        # {url, alt, nearby_text}
    lastmod: Optional[str] = None
    content_hash: str              # SHA-256 of cleaned text
    ingested_at: str               # ISO 8601 timestamp


class Chunk(BaseModel):
    """A semantic chunk derived from an article for vector and keyword search."""
    chunk_id: str
    article_id: str
    url: str
    title: str
    heading: str
    heading_path: list[str] = []
    content: str
    image_refs: list[str] = []
    chunk_index: int = 0
    token_count: int = 0
