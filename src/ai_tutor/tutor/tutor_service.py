from __future__ import annotations

import sqlite3

from ai_tutor.config import Config
from ai_tutor.kb.retrieval import find_relevant_lesson
from ai_tutor.tutor.prompts import (
    build_system_prompt, NOT_REGISTERED_REPLY, NO_CONTEXT_REPLY,
)
from ai_tutor.tutor.students import get_student


def _log_qa(conn: sqlite3.Connection, telegram_id: int, question: str,
            answer: str, lesson_id: int | None) -> None:
    conn.execute(
        "INSERT INTO qa_log(telegram_id, question, answer, lesson_id) VALUES (?,?,?,?)",
        (telegram_id, question, answer, lesson_id),
    )
    conn.commit()


def answer_question(conn: sqlite3.Connection, cfg: Config, claude,
                    telegram_id: int, name: str, question: str) -> str:
    student = get_student(conn, telegram_id)
    if student is None:
        return NOT_REGISTERED_REPLY

    hit = find_relevant_lesson(conn, cfg, student["lop"], question)
    if hit is None:
        # Tiết kiệm token: không có bài liên quan → trả lời cố định, không gọi Claude.
        _log_qa(conn, telegram_id, question, NO_CONTEXT_REPLY, None)
        return NO_CONTEXT_REPLY

    lesson_id, context = hit
    answer = claude.complete(
        build_system_prompt(student["lop"]),
        f"Câu hỏi: {question}\n\n--- TÀI LIỆU ---\n{context[:8000]}",
        smart=True,
        max_tokens=800,
    )
    _log_qa(conn, telegram_id, question, answer, lesson_id)
    return answer
