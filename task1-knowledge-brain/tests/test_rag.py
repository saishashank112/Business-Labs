"""Tests for RAG answering, citations, and escalation trigger."""

import pytest
from app.database import get_db, init_db
from app.models import Chunk
from ingestion.keyword_index import index_chunks_fts
from retrieval.rag import answer_query, load_rag_prompt


def test_load_rag_prompt():
    """RAG prompt template must load from disk and contain key rules."""
    prompt = load_rag_prompt()
    assert "EVIDENCE-BASED ANSWERING" in prompt
    assert "CITATIONS" in prompt
    assert "INJECTION DEFENSE" in prompt


@pytest.mark.asyncio
async def test_answer_query_creates_escalation_on_missing_evidence():
    """When no evidence matches, an escalation should be created in SQLite."""
    await init_db()

    # Query for something completely unrelated that has no docs
    resp = await answer_query(
        question="xyzabc nonexistent rocket science question 987654321",
        mode="keyword",
    )

    assert resp.status == "insufficient_evidence"
    assert resp.needs_human is True
    assert resp.escalation_id is not None

    # Check escalation in database
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id, status FROM escalations WHERE id = ?", (resp.escalation_id,))
        row = await cursor.fetchone()
        assert row is not None
        assert row["status"] == "open"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_answer_query_with_evidence():
    """When evidence exists, answer_query returns citations and sources."""
    await init_db()

    chunk = Chunk(
        chunk_id="c_ssl_1",
        article_id="art_ssl",
        url="https://support.brilliantdirectories.com/articles/ssl-faq",
        title="SSL & HTTPS FAQ",
        heading="Free SSL Certificates",
        content="Brilliant Directories provides free Let's Encrypt SSL certificates automatically for all domains.",
        chunk_index=0,
    )
    await index_chunks_fts([chunk])

    resp = await answer_query(
        question="Does Brilliant Directories provide free SSL?",
        mode="keyword",
    )

    assert resp.status == "answered"
    assert resp.needs_human is False
    assert len(resp.sources) >= 1
    assert "SSL & HTTPS FAQ" in [s.title for s in resp.sources]
    assert resp.request_id is not None
