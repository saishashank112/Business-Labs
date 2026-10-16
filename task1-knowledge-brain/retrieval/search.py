"""Hybrid search combining ChromaDB vector search and SQLite FTS5 keyword search.

Uses Reciprocal Rank Fusion (RRF) to merge rankings across modalities.
Also checks expert_knowledge for verified answers from resolved escalations.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

from app.database import get_db
from ingestion.keyword_index import search_keyword
from ingestion.embedder import search_vector

logger = logging.getLogger(__name__)


async def get_expert_knowledge(query: str, top_k: int = 2) -> list[dict[str, Any]]:
    """Look up expert answers from previously resolved escalations."""
    db = await get_db()
    try:
        # Check if table exists and query for matching questions
        cursor = await db.execute(
            """SELECT id, question, answer, reviewer, created_at
               FROM expert_knowledge
               WHERE reviewed = 1 AND (question LIKE ? OR answer LIKE ?)
               ORDER BY created_at DESC
               LIMIT ?""",
            (f"%{query}%", f"%{query}%", top_k),
        )
        rows = await cursor.fetchall()
        expert_results: list[dict[str, Any]] = []
        for r in rows:
            expert_results.append({
                "chunk_id": f"expert_{r['id']}",
                "article_id": f"expert_{r['id']}",
                "url": "#expert-knowledge",
                "title": f"Verified Expert Knowledge: {r['question']}",
                "heading": "Expert Verified Answer",
                "content": f"# Verified Knowledge by {r['reviewer']}\n\nQ: {r['question']}\nA: {r['answer']}",
                "score": 1.0,  # highest priority
                "image_refs": [],
                "is_expert": True,
            })
        return expert_results
    except Exception as e:
        logger.debug("No expert knowledge found or table uninitialized: %s", e)
        return []
    finally:
        await db.close()


async def hybrid_search(
    query: str,
    mode: str = "hybrid",
    top_k: int = 5,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Perform hybrid search over knowledge base chunks.

    Args:
        query: The user question or search phrase.
        mode: "vector" | "keyword" | "hybrid"
        top_k: Maximum number of chunks to return.
        rrf_k: Smoothing constant for Reciprocal Rank Fusion (default 60).

    Returns:
        List of ranked chunks with scores and metadata.
    """
    # Check expert knowledge first
    expert_hits = await get_expert_knowledge(query)

    if mode == "vector":
        try:
            vec_results = search_vector(query, top_k=top_k)
        except Exception as e:
            logger.warning("Vector search failed, falling back to keyword: %s", e)
            vec_results = []
        merged = expert_hits + vec_results
        return merged[:top_k]

    if mode == "keyword":
        kw_results = await search_keyword(query, top_k=top_k)
        merged = expert_hits + kw_results
        return merged[:top_k]

    # Hybrid mode (Vector + Keyword with RRF)
    try:
        vec_results = search_vector(query, top_k=top_k * 2)
    except Exception as e:
        logger.warning("Vector search failed in hybrid search: %s", e)
        vec_results = []

    try:
        kw_results = await search_keyword(query, top_k=top_k * 2)
    except Exception as e:
        logger.warning("Keyword search failed in hybrid search: %s", e)
        kw_results = []

    # Map chunks by chunk_id
    all_chunks: dict[str, dict[str, Any]] = {}
    rrf_scores: dict[str, float] = {}

    # Rank positions (1-indexed)
    for rank, item in enumerate(vec_results, start=1):
        cid = item["chunk_id"]
        all_chunks[cid] = item
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank))

    for rank, item in enumerate(kw_results, start=1):
        cid = item["chunk_id"]
        if cid not in all_chunks:
            all_chunks[cid] = item
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank))

    # Sort by combined RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    ranked_results: list[dict[str, Any]] = []
    max_rrf = max(rrf_scores.values()) if rrf_scores else 1.0

    for cid in sorted_ids[:top_k]:
        chunk_data = dict(all_chunks[cid])
        # Normalize score between 0 and 1
        chunk_data["score"] = round(rrf_scores[cid] / max_rrf, 4)
        ranked_results.append(chunk_data)

    merged = expert_hits + ranked_results
    return merged[:top_k]
