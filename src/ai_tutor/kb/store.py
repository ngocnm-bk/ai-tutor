from __future__ import annotations

import sqlite3

from ai_tutor.classify.types import Classification
from ai_tutor.config import Config
from ai_tutor.kb.paths import lesson_dir


def _find_or_create_skill(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM skills WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO skills(name) VALUES(?)", (name,))
    return cur.lastrowid


def find_or_create_lesson(conn: sqlite3.Connection, cfg: Config,
                          c: Classification) -> int:
    dir_path = lesson_dir(cfg.kb_dir, c)
    key = str(dir_path)
    row = conn.execute("SELECT id FROM lessons WHERE dir_path=?", (key,)).fetchone()
    if row:
        return row["id"]
    dir_path.mkdir(parents=True, exist_ok=True)
    cur = conn.execute(
        "INSERT INTO lessons(mon, lop, chuong, bai, dir_path) VALUES (?,?,?,?,?)",
        (c.mon, c.lop, c.chuong, c.bai, key),
    )
    lesson_id = cur.lastrowid
    for skill in c.ky_nang:
        skill_id = _find_or_create_skill(conn, skill)
        conn.execute(
            "INSERT OR IGNORE INTO lesson_skills(lesson_id, skill_id) VALUES (?,?)",
            (lesson_id, skill_id),
        )
    conn.commit()
    return lesson_id


def assign_document_to_lesson(conn: sqlite3.Connection, doc_id: int,
                              lesson_id: int) -> None:
    conn.execute(
        "UPDATE documents SET lesson_id=?, status='classified' WHERE id=?",
        (lesson_id, doc_id),
    )
    conn.commit()
