import aiosqlite
from app.config import settings


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(settings.t3_db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcripts (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    label           TEXT,
    meeting_date    TEXT,
    content         TEXT NOT NULL,
    is_follow_up    INTEGER DEFAULT 0,
    parent_transcript_id TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirements (
    id              TEXT PRIMARY KEY,
    transcript_id   TEXT REFERENCES transcripts(id),
    project_id      TEXT REFERENCES projects(id),
    description     TEXT NOT NULL,
    source_quote    TEXT,
    status          TEXT DEFAULT 'confirmed',
    priority        TEXT,
    stated_or_inferred TEXT,
    feasibility     TEXT,
    feasibility_detail TEXT,
    existing_solution TEXT,
    acceptance_criteria TEXT,
    dependencies    TEXT,
    estimate_status TEXT DEFAULT 'pending',
    version         INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS scope_versions (
    id              TEXT PRIMARY KEY,
    project_id      TEXT REFERENCES projects(id),
    version         INTEGER NOT NULL,
    content         TEXT NOT NULL,
    status          TEXT DEFAULT 'draft',
    approved_by     TEXT,
    approved_at     TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS estimates (
    id              TEXT PRIMARY KEY,
    scope_version_id TEXT REFERENCES scope_versions(id),
    project_id      TEXT REFERENCES projects(id),
    tasks           TEXT NOT NULL,
    hourly_rate     REAL,
    currency        TEXT DEFAULT 'USD',
    tax_rate        REAL DEFAULT 0,
    total_likely_hours REAL,
    estimated_cost_likely REAL,
    version         INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    id              TEXT PRIMARY KEY,
    project_id      TEXT REFERENCES projects(id),
    scope_version_id TEXT,
    estimate_id     TEXT,
    content         TEXT NOT NULL,
    version         INTEGER DEFAULT 1,
    status          TEXT DEFAULT 'draft',
    approved_by     TEXT,
    approved_at     TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS change_reports (
    id              TEXT PRIMARY KEY,
    project_id      TEXT REFERENCES projects(id),
    baseline_scope_id TEXT,
    new_transcript_id TEXT,
    added           TEXT,
    modified        TEXT,
    removed         TEXT,
    out_of_scope    TEXT,
    conflicts       TEXT,
    summary         TEXT,
    created_at      TEXT NOT NULL
);

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
