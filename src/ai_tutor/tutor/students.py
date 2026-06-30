from __future__ import annotations

import sqlite3


def register_student(conn: sqlite3.Connection, telegram_id: int, name: str,
                     lop: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO students(telegram_id, name, lop) VALUES (?,?,?)",
        (telegram_id, name, lop),
    )
    conn.commit()


def get_student(conn: sqlite3.Connection, telegram_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT telegram_id, name, lop FROM students WHERE telegram_id=?",
        (telegram_id,),
    ).fetchone()
