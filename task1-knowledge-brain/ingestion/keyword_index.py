"""SQLite FTS5 full-text search index for keyword retrieval.

Implements BM25 search over chunk content, title, and headings.
"""

from __future__ import annotations

import re
from typing import List, Dict, Any

from app.database import get_db
from app.models import Chunk


FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    article_id UNINDEXED,
    url UNINDEXED,
    title,
    heading,
    content,
    tokenize = 'porter unicode61'
);
"""


def clean_fts_query(query: str) -> str:
    """Sanitize user query for SQLite FTS5 MATCH syntax.
    
    Removes syntax characters that cause FTS5 parse errors, splits into terms,
    and returns an OR or AND expression.
    """
    # Keep alphanumeric characters and spaces
    cleaned = re.sub(r"[^\w\s]", " ", query).strip()
    words = [w for w in cleaned.split() if len(w) > 1]
    if not words:
        return '""'
    # Match query words with prefix wildcards for flexible keyword matching
    # e.g. "payment gateway" -> '"payment"* OR "gateway"*'
    return " OR ".join([f'"{w}"*' for w in words])


async def init_fts_table() -> None:
    """Ensure FTS5 virtual table exists."""
    db = await get_db()
    try:
        await db.execute(FTS_SCHEMA)
        await db.commit()
    finally:
        await db.close()


async def index_chunks_fts(chunks: list[Chunk]) -> None:
    """Insert or replace chunks into the FTS5 index."""
    if not chunks:
        return

    await init_fts_table()
    db = await get_db()
    try:
        for chunk in chunks:
            # Delete existing row for this chunk_id if present
            await db.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk.chunk_id,))
            await db.execute(
                """INSERT INTO chunks_fts (chunk_id, article_id, url, title, heading, content)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    chunk.chunk_id,
                    chunk.article_id,
                    chunk.url,
                    chunk.title,
                    chunk.heading,
                    chunk.content,
                ),
            )
        await db.commit()
    finally:
        await db.close()


async def search_keyword(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Search FTS5 index using BM25 ranking.
    
    Returns list of dicts:
        {
            "chunk_id": str,
            "article_id": str,
            "url": str,
            "title": str,
            "heading": str,
            "content": str,
            "score": float  # Normalized 0.0 - 1.0 (higher is better)
        }
    """
    await init_fts_table()
    match_query = clean_fts_query(query)
    if match_query == '""':
        return []

    db = await get_db()
    try:
        # SQLite FTS5 bm25() returns negative numbers where more negative = better match
        cursor = await db.execute(
            """SELECT chunk_id, article_id, url, title, heading, content, bm25(chunks_fts) as rank
               FROM chunks_fts
               WHERE chunks_fts MATCH ?
               ORDER BY rank ASC
               LIMIT ?""",
            (match_query, top_k),
        )
        rows = await cursor.fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            # Normalize bm25 rank (e.g. -5.2 -> ~0.84)
            raw_rank = float(row["rank"])
            normalized_score = 1.0 / (1.0 + abs(raw_rank)) if raw_rank <= 0 else 1.0 / (1.0 + raw_rank)

            results.append({
                "chunk_id": row["chunk_id"],
                "article_id": row["article_id"],
                "url": row["url"],
                "title": row["title"],
                "heading": row["heading"],
                "content": row["content"],
                "score": round(normalized_score, 4),
            })
        return results
    except Exception:
        # If FTS fails for some reason (e.g. empty or special syntax), fall back to simple LIKE search
        cursor = await db.execute(
            """SELECT chunk_id, article_id, url, title, heading, content
               FROM chunks_fts
               WHERE content LIKE ? OR title LIKE ?
               LIMIT ?""",
            (f"%{query}%", f"%{query}%", top_k),
        )
        rows = await cursor.fetchall()
        return [
            {
                "chunk_id": row["chunk_id"],
                "article_id": row["article_id"],
                "url": row["url"],
                "title": row["title"],
                "heading": row["heading"],
                "content": row["content"],
                "score": 0.5,
            }
            for row in rows
        ]
    finally:
        await db.close()
