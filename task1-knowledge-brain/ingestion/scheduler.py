"""Ingestion scheduler using APScheduler.

Runs daily background crawl to keep the Knowledge Brain synchronized
with the Brilliant Directories Solution Center.
"""

from __future__ import annotations

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ingestion.pipeline import run_ingestion_pipeline

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def scheduled_crawl_job() -> None:
    """Invoked on schedule by APScheduler."""
    logger.info("Executing scheduled daily knowledge ingestion...")
    try:
        report = await run_ingestion_pipeline()
        logger.info("Scheduled ingestion complete: %s", report)
    except Exception as e:
        logger.error("Scheduled ingestion failed: %s", e)


def start_scheduler() -> AsyncIOScheduler:
    """Start the APScheduler for daily background ingestion."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler()
    # Run once daily at 03:00 AM UTC
    _scheduler.add_job(
        scheduled_crawl_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="daily_crawl",
        name="Daily Brilliant Directories Knowledge Crawl",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("APScheduler started: daily crawl scheduled for 03:00 UTC")
    return _scheduler


def shutdown_scheduler() -> None:
    """Shut down scheduler gracefully."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
