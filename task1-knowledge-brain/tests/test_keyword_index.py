"""Tests for SQLite FTS5 keyword indexing and search."""

import pytest
from app.models import Chunk
from ingestion.keyword_index import clean_fts_query, index_chunks_fts, search_keyword


def test_clean_fts_query():
    """clean_fts_query should strip punctuation and format wildcard terms."""
    q = clean_fts_query("How do I set up Stripe???")
    assert '"How"*' in q
    assert '"Stripe"*' in q
    assert "?" not in q


@pytest.mark.asyncio
async def test_index_and_search_fts():
    """FTS5 index should store chunks and return matches ordered by rank."""
    chunk1 = Chunk(
        chunk_id="test_c1",
        article_id="art1",
        url="https://example.com/art1",
        title="Configuring Stripe Payments",
        heading="Stripe Setup",
        content="In Brilliant Directories, navigate to Finance then Payment Gateways to enable Stripe.",
        chunk_index=0,
    )
    chunk2 = Chunk(
        chunk_id="test_c2",
        article_id="art2",
        url="https://example.com/art2",
        title="Custom CSS Rules",
        heading="Styling",
        content="Use the design settings panel to insert custom CSS rules for headers and footers.",
        chunk_index=0,
    )

    await index_chunks_fts([chunk1, chunk2])

    results = await search_keyword("Stripe payment")
    assert len(results) >= 1
    assert results[0]["chunk_id"] == "test_c1"
    assert "Stripe" in results[0]["title"]
    assert results[0]["score"] > 0
