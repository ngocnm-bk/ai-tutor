from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path

from ai_tutor.config import Config


def _tokens(s: str) -> set[str]:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return {t for t in re.split(r"[^a-z0-9]+", s) if len(t) > 0}


def find_relevant_lesson(conn: sqlite3.Connection, cfg: Config, lop: int,
                         question: str) -> tuple[int, str] | None:
    q_tokens = _tokens(question)
    if not q_tokens:
        return None
    best_id: int | None = None
    best_body = ""
    best_score = 0
    rows = conn.execute(
        "SELECT id, chuong, bai, dir_path FROM lessons WHERE lop=?", (lop,)
    ).fetchall()
    for row in rows:
        md_path = Path(row["dir_path"]) / "lesson.md"
        body = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        haystack = _tokens(f"{row['chuong'] or ''} {row['bai'] or ''} {body}")
        score = len(q_tokens & haystack)
        if score > best_score:
            best_score, best_id, best_body = score, row["id"], body
    if best_id is None:
        return None
    return best_id, best_body
