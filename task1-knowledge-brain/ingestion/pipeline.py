"""Ingestion pipeline — orchestrates: sitemap → crawl → parse → store.

This is the single function called by the /ingestion/run route.
Each step is in its own module; this file just wires them together.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import settings
from app.database import get_db
from ingestion.sitemap import fetch_sitemap
from ingestion.crawler import crawl_pages
from ingestion.parser import parse_html_to_article

logger = logging.getLogger(__name__)


async def run_ingestion_pipeline(
    max_pages: int | None = None,
) -> dict:
    """Run the full ingestion pipeline and return a report.

    Steps:
        1. Fetch sitemap → list of article URLs
        2. Compare with manifest → decide what to crawl
        3. Crawl new/changed pages (polite, resumable)
        4. Parse HTML → structured article JSON
        5. Store articles in SQLite (insert or update)
        6. Detect removed pages

    Args:
        max_pages: Override the config limit (for testing).

    Returns:
        Report dict: {added, updated, removed, failed, unchanged}
    """
    report = {"added": 0, "updated": 0, "removed": 0, "failed": 0, "unchanged": 0}
    limit = max_pages or settings.t1_crawl_max_pages

    # Ensure tables exist
    from app.database import init_db
    await init_db()

    # ── Step 1: Fetch sitemap ───────────────────────────────
    logger.info("Fetching sitemap from %s", settings.t1_sitemap_url)
    entries = await fetch_sitemap(settings.t1_sitemap_url)
    logger.info("Found %d article URLs in sitemap", len(entries))

    # Limit for testing
    if limit and len(entries) > limit:
        logger.info("Limiting to %d pages (config)", limit)
        entries = entries[:limit]

    # ── Step 2: Check manifest for what's changed ───────────
    sitemap_urls = {e.url for e in entries}
    db = await get_db()
    try:
        cursor = await db.execute("SELECT url, content_hash FROM articles")
        existing = {row[0]: row[1] for row in await cursor.fetchall()}
    finally:
        await db.close()

    # ── Step 3: Crawl pages ─────────────────────────────────
    logger.info("Starting crawl of %d pages...", len(entries))
    results = await crawl_pages(entries)

    # ── Step 4 & 5: Parse and store ─────────────────────────
    for result in results:
        if result.status != "fetched" or result.html is None:
            report["failed"] += 1
            continue

        article = parse_html_to_article(
            html=result.html,
            url=result.url,
            lastmod=result.lastmod,
        )
        if article is None:
            logger.warning("Could not parse article from %s", result.url)
            report["failed"] += 1
            continue

        # Store in database
        db = await get_db()
        should_index = False
        try:
            if article.url in existing:
                if existing[article.url] == article.content_hash:
                    report["unchanged"] += 1
                else:
                    await db.execute(
                        """UPDATE articles
                           SET title=?, content_json=?, content_hash=?,
                               lastmod=?, ingested_at=?, version = version + 1
                           WHERE url=?""",
                        (
                            article.title,
                            article.model_dump_json(),
                            article.content_hash,
                            article.lastmod,
                            article.ingested_at,
                            article.url,
                        ),
                    )
                    await db.commit()
                    report["updated"] += 1
                    should_index = True
                    logger.info("Updated: %s", article.title)
            else:
                await db.execute(
                    """INSERT INTO articles
                       (id, url, title, content_json, content_hash, lastmod, ingested_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        article.id,
                        article.url,
                        article.title,
                        article.model_dump_json(),
                        article.content_hash,
                        article.lastmod,
                        article.ingested_at,
                    ),
                )
                await db.commit()
                report["added"] += 1
                should_index = True
                logger.info("Added: %s", article.title)
        finally:
            await db.close()

        # Chunk and index newly added or updated article
        if should_index:
            try:
                from ingestion.chunker import chunk_article
                from ingestion.keyword_index import index_chunks_fts
                from ingestion.embedder import upsert_chunks_vector

                chunks = chunk_article(article)
                await index_chunks_fts(chunks)
                try:
                    upsert_chunks_vector(chunks)
                except Exception as vec_err:
                    logger.warning("Could not upsert vector chunks for %s: %s", article.title, vec_err)
            except Exception as idx_err:
                logger.error("Failed to chunk and index article %s: %s", article.title, idx_err)

    # ── Step 6: Detect removed pages ────────────────────────
    removed_urls = set(existing.keys()) - sitemap_urls
    if removed_urls:
        db = await get_db()
        try:
            for url in removed_urls:
                await db.execute("DELETE FROM articles WHERE url = ?", (url,))
                await db.execute(
                    """UPDATE manifest SET status = 'removed', updated_at = ?
                       WHERE url = ?""",
                    (datetime.now(timezone.utc).isoformat(), url),
                )
            await db.commit()
            report["removed"] = len(removed_urls)
            logger.info("Removed %d articles no longer in sitemap", len(removed_urls))
        finally:
            await db.close()

    # ── Print report ────────────────────────────────────────
    logger.info(
        "Ingestion complete: added=%d, updated=%d, unchanged=%d, removed=%d, failed=%d",
        report["added"], report["updated"], report["unchanged"],
        report["removed"], report["failed"],
    )
    return report


async def index_stored_articles() -> int:
    """Index all articles currently in the SQLite articles table into FTS5 and ChromaDB.
    
    Returns total chunks indexed.
    """
    from app.database import get_db, init_db
    from app.models import ParsedArticle
    from ingestion.chunker import chunk_article
    from ingestion.keyword_index import index_chunks_fts
    from ingestion.embedder import upsert_chunks_vector

    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute("SELECT content_json FROM articles")
        rows = await cursor.fetchall()
    finally:
        await db.close()

    total_chunks = 0
    for row in rows:
        try:
            article = ParsedArticle.model_validate_json(row["content_json"])
            chunks = chunk_article(article)
            if chunks:
                await index_chunks_fts(chunks)
                try:
                    upsert_chunks_vector(chunks)
                except Exception as e:
                    logger.warning("Could not upsert vector chunks for %s: %s", article.title, e)
                total_chunks += len(chunks)
        except Exception as err:
            logger.error("Failed to parse/index stored article: %s", err)

    logger.info("Successfully indexed %d chunks across %d articles", total_chunks, len(rows))
    return total_chunks
