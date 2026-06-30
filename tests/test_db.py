from pathlib import Path
import sqlite3
import pytest
from ai_tutor.db import connect, init_db


def test_init_db_creates_tables(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"documents", "lessons", "skills",
            "lesson_skills", "students", "qa_log"} <= names


def test_init_db_is_idempotent(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    init_db(conn)
    init_db(conn)  # không được lỗi


def test_documents_content_hash_unique(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    init_db(conn)
    conn.execute("INSERT INTO documents(content_hash, source_path, file_type, status) "
                 "VALUES('h1','a.txt','text','ingested')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO documents(content_hash, source_path, file_type, status) "
                     "VALUES('h1','b.txt','text','ingested')")
