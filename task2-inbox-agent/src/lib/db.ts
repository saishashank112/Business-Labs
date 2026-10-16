import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const { DatabaseSync } = require("node:sqlite");

let dbInstance: DatabaseSync | null = null;

export function getDb(): DatabaseSync {
  if (dbInstance) {
    return dbInstance;
  }

  // Database file stored locally in project folder
  const dbPath = path.resolve(process.cwd(), "task2.db");
  dbInstance = new DatabaseSync(dbPath);

  // Initialize schema
  dbInstance.exec(`
    PRAGMA journal_mode = WAL;

    CREATE TABLE IF NOT EXISTS interactions (
      id TEXT PRIMARY KEY,
      email_file TEXT NOT NULL,
      email_subject TEXT,
      email_body TEXT NOT NULL,
      predicted_category TEXT,
      predicted_risk TEXT,
      urgency TEXT,
      knowledge_query TEXT,
      knowledge_response TEXT,
      sources TEXT,
      draft_text TEXT,
      draft_schema TEXT,
      human_action TEXT,
      human_edit TEXT,
      correction_reason TEXT,
      final_text TEXT,
      model TEXT,
      prompt_version TEXT,
      outcome TEXT,
      created_at TEXT NOT NULL,
      reviewed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS auto_send_rules (
      kind TEXT PRIMARY KEY,
      consecutive_unchanged INTEGER DEFAULT 0,
      eligible INTEGER DEFAULT 0,
      enabled INTEGER DEFAULT 0,
      disabled_reason TEXT,
      updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS auto_send_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      kind TEXT NOT NULL,
      action TEXT NOT NULL,
      detail TEXT,
      interaction_id TEXT,
      timestamp TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS prompt_versions (
      name TEXT NOT NULL,
      version INTEGER NOT NULL,
      file_path TEXT NOT NULL,
      active INTEGER DEFAULT 0,
      created_at TEXT NOT NULL,
      PRIMARY KEY (name, version)
    );

    CREATE TABLE IF NOT EXISTS llm_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      request_id TEXT,
      step TEXT,
      model TEXT,
      provider TEXT,
      input_tokens INTEGER,
      output_tokens INTEGER,
      latency_ms INTEGER,
      cost_usd REAL,
      timestamp TEXT NOT NULL
    );
  `);

  return dbInstance;
}
