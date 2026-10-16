"""Polite, resumable async crawler.

Key behaviors (all from PRD FR-1.3):
  - Reads robots.txt before starting
  - Configurable delay between requests (default 1s)
  - Configurable concurrency (default 2 workers)
  - Exponential backoff on failure: delay * 2^attempt
  - Retry limit per page (default 3)
  - Saves status to manifest after every page
  - One failed page never stops the whole job
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.database import get_db
from app.models import SitemapEntry
from ingestion.robots_parser import WildcardRobotParser

logger = logging.getLogger(__name__)


# ── Result type for one crawled page ────────────────────────

class CrawlResult:
    """Result of crawling a single URL."""

    def __init__(
        self,
        url: str,
        status: str,         # "fetched" | "skipped" | "failed"
        html: str | None = None,
        lastmod: str | None = None,
        error: str | None = None,
    ):
        self.url = url
        self.status = status
        self.html = html
        self.lastmod = lastmod
        self.error = error


# ── Robots.txt checker ──────────────────────────────────────

async def load_robots_txt(base_url: str) -> WildcardRobotParser:
    """Fetch robots.txt and return a wildcard/anchor-aware parser we can query."""
    robots_url = base_url.rstrip("/") + "/robots.txt"
    parser = WildcardRobotParser()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(robots_url)
            parser.parse(resp.text.splitlines())
    except Exception as exc:
        logger.warning("Could not fetch robots.txt: %s — allowing all", exc)
        parser.allow_all = True

    return parser


# ── Core crawler ────────────────────────────────────────────

async def crawl_pages(
    entries: list[SitemapEntry],
    delay: float | None = None,
    concurrency: int | None = None,
    max_retries: int | None = None,
    limit: int | None = None,
    resume: bool = True,
) -> list[CrawlResult]:
    """Crawl a list of sitemap entries politely and return results.

    Args:
        entries:     URLs to crawl (from sitemap parser).
        delay:       Seconds between requests per worker (default from config).
        concurrency: Max parallel requests (default from config).
        max_retries: Give up after this many failures (default from config).

    Returns:
        One CrawlResult per entry — check .status for success/failure.
    """
    delay = delay or settings.t1_crawl_delay
    concurrency = concurrency or settings.t1_crawl_concurrency
    max_retries = max_retries or settings.t1_crawl_max_retries

    if limit is not None and len(entries) > limit:
        logger.info("Applying crawl limit: processing %d of %d pages", limit, len(entries))
        entries = entries[:limit]

    semaphore = asyncio.Semaphore(concurrency)

    # Load robots.txt once for the whole crawl
    base_url = "https://support.brilliantdirectories.com"
    robots = await load_robots_txt(base_url)

    # Global rate limiter ensuring delay applies across all concurrent workers
    global_rate_lock = asyncio.Lock()
    last_req_time: float = 0.0

    async def throttle():
        nonlocal last_req_time
        async with global_rate_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - last_req_time
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
            last_req_time = asyncio.get_event_loop().time()

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "AITechConsultant-Bot/1.0 (educational project)"},
    ) as client:

        async def fetch_one(entry: SitemapEntry) -> CrawlResult:
            """Fetch one page with retries, resume check, and backoff."""
            # Check manifest for resume
            if resume and await _is_already_fetched(entry.url):
                logger.info("Resuming: URL already fetched according to manifest: %s", entry.url)
                return CrawlResult(url=entry.url, status="skipped", error="already_fetched")

            # Check robots.txt
            if not robots.can_fetch("*", entry.url):
                logger.info("Blocked by robots.txt: %s", entry.url)
                await _update_manifest(entry.url, "skipped", error="robots.txt")
                return CrawlResult(url=entry.url, status="skipped", error="robots.txt")

            for attempt in range(max_retries):  # type: ignore[arg-type]
                async with semaphore:
                    try:
                        # Polite throttle applied globally across all workers
                        if attempt > 0:
                            backoff = delay * (2 ** attempt)  # type: ignore[operator]
                            logger.info("Retry %d for %s (backoff %.1fs)", attempt, entry.url, backoff)
                            await asyncio.sleep(backoff)
                        else:
                            await throttle()

                        resp = await client.get(entry.url)
                        resp.raise_for_status()

                        await _update_manifest(
                            entry.url, "fetched", attempts=attempt + 1
                        )
                        return CrawlResult(
                            url=entry.url,
                            status="fetched",
                            html=resp.text,
                            lastmod=entry.lastmod,
                        )

                    except Exception as exc:
                        logger.warning(
                            "Attempt %d failed for %s: %s", attempt + 1, entry.url, exc
                        )
                        await _update_manifest(
                            entry.url, "failed",
                            attempts=attempt + 1,
                            error=str(exc),
                        )

            # All retries exhausted
            return CrawlResult(url=entry.url, status="failed", error="max retries exceeded")

        # Run all fetches concurrently (semaphore controls parallelism)
        tasks = [fetch_one(entry) for entry in entries]
        results = await asyncio.gather(*tasks)

    return list(results)


async def _is_already_fetched(url: str) -> bool:
    """Check if URL was already fetched in manifest."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT status FROM manifest WHERE url = ?", (url,))
        row = await cursor.fetchone()
        return bool(row and row[0] == "fetched")
    except Exception:
        return False
    finally:
        await db.close()


# ── Manifest helpers ────────────────────────────────────────

async def _update_manifest(
    url: str,
    status: str,
    attempts: int = 0,
    error: str | None = None,
) -> None:
    """Insert or update one row in the manifest table."""
    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO manifest (url, status, attempts, last_error, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET
                   status = excluded.status,
                   attempts = excluded.attempts,
                   last_error = excluded.last_error,
                   updated_at = excluded.updated_at
            """,
            (url, status, attempts, error, now),
        )
        await db.commit()
    finally:
        await db.close()
