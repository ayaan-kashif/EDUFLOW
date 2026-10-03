import { DatabaseSync } from "node:sqlite";
import path from "node:path";
import fs from "node:fs";

function findDatabasePath(): string {
  if (process.env.DATABASE_URL && process.env.DATABASE_URL.startsWith("file:")) {
    const raw = process.env.DATABASE_URL.replace(/^file:/, "");
    return path.resolve(/*turbopackIgnore: true*/ process.cwd(), raw);
  }
  const rootDb = path.resolve(/*turbopackIgnore: true*/ process.cwd(), "..", "curriculumos.db");
  if (fs.existsSync(/*turbopackIgnore: true*/ rootDb)) {
    return rootDb;
  }
  return path.resolve(/*turbopackIgnore: true*/ process.cwd(), "curriculumos.db");
}

let dbInstance: DatabaseSync | null = null;

export function getDb(): DatabaseSync {
  if (dbInstance) return dbInstance;

  const dbPath = findDatabasePath();
  const db = new DatabaseSync(dbPath);

  // Enable WAL mode & foreign keys for SQLite performance and integrity
  try {
    db.exec("PRAGMA journal_mode = WAL;");
    db.exec("PRAGMA foreign_keys = ON;");
  } catch (err) {
    console.warn("Could not set PRAGMA:", err);
  }

  // Ensure tables exist if running against a fresh DB
  db.exec(`
    CREATE TABLE IF NOT EXISTS portal_users (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL,
      enrollment_code TEXT UNIQUE,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS portal_sessions (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
      token_hash TEXT UNIQUE NOT NULL,
      expires_at DATETIME NOT NULL
    );

    CREATE TABLE IF NOT EXISTS teacher_enrollments (
      teacher_id TEXT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
      student_id TEXT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
      PRIMARY KEY (teacher_id, student_id)
    );

    CREATE TABLE IF NOT EXISTS class_outlines (
      id TEXT PRIMARY KEY,
      teacher_id TEXT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      subject TEXT NOT NULL,
      content TEXT NOT NULL,
      source_text TEXT,
      published INTEGER NOT NULL DEFAULT 0,
      notes TEXT,
      study_plan TEXT,
      generated_by TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS curriculum_nodes (
      id TEXT PRIMARY KEY,
      node_type TEXT NOT NULL,
      label TEXT NOT NULL,
      description TEXT,
      syllabus_ref TEXT,
      origin TEXT NOT NULL,
      confidence REAL NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS curriculum_edges (
      id TEXT PRIMARY KEY,
      from_node_id TEXT NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
      to_node_id TEXT NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
      edge_type TEXT NOT NULL,
      confidence REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS source_documents (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      doc_type TEXT NOT NULL,
      sha256 TEXT NOT NULL,
      page_count INTEGER NOT NULL,
      uri TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS source_spans (
      id TEXT PRIMARY KEY,
      document_id TEXT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
      page_number INTEGER NOT NULL,
      start_char INTEGER NOT NULL,
      end_char INTEGER NOT NULL,
      text_snippet TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS plan_versions (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      version_number INTEGER NOT NULL,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS academic_calendars (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      academic_year TEXT NOT NULL,
      start_date TEXT NOT NULL,
      end_date TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS calendar_days (
      id TEXT PRIMARY KEY,
      calendar_id TEXT NOT NULL REFERENCES academic_calendars(id) ON DELETE CASCADE,
      date TEXT NOT NULL,
      day_type TEXT NOT NULL,
      notes TEXT
    );

    CREATE TABLE IF NOT EXISTS teaching_units (
      id TEXT PRIMARY KEY,
      node_id TEXT NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      duration_minutes INTEGER NOT NULL,
      order_index INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS scheduled_units (
      id TEXT PRIMARY KEY,
      plan_version_id TEXT NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
      unit_id TEXT NOT NULL REFERENCES teaching_units(id) ON DELETE CASCADE,
      calendar_day_id TEXT NOT NULL REFERENCES calendar_days(id) ON DELETE CASCADE,
      order_index INTEGER NOT NULL,
      status TEXT NOT NULL,
      notes TEXT
    );

    CREATE TABLE IF NOT EXISTS claims (
      id TEXT PRIMARY KEY,
      unit_id TEXT REFERENCES teaching_units(id) ON DELETE SET NULL,
      claim_text TEXT NOT NULL,
      verification_status TEXT NOT NULL,
      confidence REAL NOT NULL,
      source_page INTEGER,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS claim_evidence (
      claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
      source_span_id TEXT NOT NULL REFERENCES source_spans(id) ON DELETE CASCADE,
      PRIMARY KEY (claim_id, source_span_id)
    );

    CREATE TABLE IF NOT EXISTS class_mastery_signals (
      id TEXT PRIMARY KEY,
      node_id TEXT NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
      class_group TEXT NOT NULL,
      mastery_percentage REAL NOT NULL,
      status TEXT NOT NULL,
      recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS teacher_corrections (
      id TEXT PRIMARY KEY,
      entity_type TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      correction_data TEXT NOT NULL,
      comment TEXT,
      applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);

  dbInstance = db;
  return dbInstance;
}
