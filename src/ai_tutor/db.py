from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY,
    content_hash  TEXT NOT NULL UNIQUE,
    source_path   TEXT NOT NULL,
    file_type     TEXT NOT NULL,
    status        TEXT NOT NULL,
    extracted_text TEXT,
    lesson_id     INTEGER REFERENCES lessons(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lessons (
    id          INTEGER PRIMARY KEY,
    mon         TEXT NOT NULL,
    lop         INTEGER NOT NULL,
    chuong      TEXT,
    bai         TEXT,
    dir_path    TEXT NOT NULL UNIQUE,
    source_hash TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skills (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lesson_skills (
    lesson_id INTEGER NOT NULL REFERENCES lessons(id),
    skill_id  INTEGER NOT NULL REFERENCES skills(id),
    PRIMARY KEY (lesson_id, skill_id)
);

CREATE TABLE IF NOT EXISTS students (
    telegram_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    lop         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_log (
    id          INTEGER PRIMARY KEY,
    telegram_id INTEGER NOT NULL,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    lesson_id   INTEGER REFERENCES lessons(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
