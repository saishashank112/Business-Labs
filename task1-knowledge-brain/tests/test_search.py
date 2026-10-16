"""Tests for hybrid search and expert knowledge integration."""

import pytest
from app.database import get_db, init_db
from app.models import Chunk
from ingestion.keyword_index import index_chunks_fts
from retrieval.search import hybrid_search, get_expert_knowledge


@pytest.mark.asyncio
async def test_expert_knowledge_prioritization():
    """Expert knowledge from resolved escalations should return top priority."""
    await init_db()
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO expert_knowledge
               (id, question, answer, reviewed, reviewer, created_at)
               VALUES (?, ?, ?, 1, ?, datetime('now'))""",
            (
                "ek-test-1",
                "How do I integrate Stripe Connect with custom commission fees?",
                "To integrate Stripe Connect custom commissions, use the Webhook addon and set fee percentage in Admin.",
                "Jane Expert",
            ),
        )
        await db.commit()
    finally:
        await db.close()

    # Query expert knowledge directly
    expert_hits = await get_expert_knowledge("Stripe Connect custom commission")
    assert len(expert_hits) >= 1
    assert expert_hits[0]["is_expert"] is True
    assert expert_hits[0]["score"] == 1.0
    assert "Jane Expert" in expert_hits[0]["content"]

    # Hybrid search should include the expert hit
    results = await hybrid_search("Stripe Connect custom commission", mode="keyword")
    assert len(results) >= 1
    assert any(r.get("is_expert") for r in results)
