"""SQLite database — table creation and connection helper.

Uses aiosqlite so database calls work inside async FastAPI routes
and the async crawler without blocking.
"""

import aiosqlite

from app.config import settings


async def get_db() -> aiosqlite.Connection:
    """Open a new database connection.

    Caller is responsible for closing it when done:
        db = await get_db()
        try:
            ...
        finally:
            await db.close()
    """
    db = await aiosqlite.connect(settings.t1_db_path)
    db.row_factory = aiosqlite.Row          # access columns by name
    await db.execute("PRAGMA journal_mode=WAL")  # better for concurrency
    return db


async def init_db() -> None:
    """Create all tables if they don't exist yet.

    Called once on server startup (see main.py lifespan).
    """
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()


# ── Table definitions ───────────────────────────────────────
SCHEMA = """
-- Crawl manifest: one row per URL found in the sitemap
CREATE TABLE IF NOT EXISTS manifest (
    url             TEXT PRIMARY KEY,
    lastmod         TEXT,
    content_hash    TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    attempts        INTEGER DEFAULT 0,
    last_error      TEXT,
    updated_at      TEXT NOT NULL
);

-- Parsed articles
CREATE TABLE IF NOT EXISTS articles (
    id              TEXT PRIMARY KEY,
    url             TEXT NOT NULL UNIQUE,
    title           TEXT,
    content_json    TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    lastmod         TEXT,
    ingested_at     TEXT NOT NULL,
    version         INTEGER DEFAULT 1
);

-- Image descriptions cached by image hash
CREATE TABLE IF NOT EXISTS image_descriptions (
    image_hash      TEXT PRIMARY KEY,
    image_url       TEXT NOT NULL,
    article_id      TEXT NOT NULL,
    description     TEXT NOT NULL,
    uncertainty     TEXT,
    model_used      TEXT,
    created_at      TEXT NOT NULL
);

-- Escalation tasks
CREATE TABLE IF NOT EXISTS escalations (
    id              TEXT PRIMARY KEY,
    question        TEXT NOT NULL,
    evidence        TEXT,
    reason          TEXT,
    status          TEXT DEFAULT 'open',
    created_at      TEXT NOT NULL,
    resolved_at     TEXT,
    resolver        TEXT,
    request_id      TEXT
);

-- Expert knowledge from resolved escalations
CREATE TABLE IF NOT EXISTS expert_knowledge (
    id              TEXT PRIMARY KEY,
    escalation_id   TEXT REFERENCES escalations(id),
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    reviewed        INTEGER DEFAULT 0,
    reviewer        TEXT,
    version         INTEGER DEFAULT 1,
    expires_at      TEXT,
    created_at      TEXT NOT NULL
);

-- LLM call log (tokens, cost, latency per call)
CREATE TABLE IF NOT EXISTS llm_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      TEXT,
    step            TEXT,
    model           TEXT,
    provider        TEXT,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    latency_ms      INTEGER,
    cost_usd        REAL,
    timestamp       TEXT NOT NULL
);
"""
