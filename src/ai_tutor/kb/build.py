from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ai_tutor.classify.classifier import classify_document
from ai_tutor.config import Config
from ai_tutor.kb.store import find_or_create_lesson, assign_document_to_lesson
from ai_tutor.synthesize.synthesizer import synthesize_lesson


@dataclass
class BuildReport:
    classified: int = 0
    lessons_touched: int = 0
    synthesized: int = 0


def build_kb(cfg: Config, conn: sqlite3.Connection, claude) -> BuildReport:
    report = BuildReport()
    touched: set[int] = set()

    pending = conn.execute(
        "SELECT id, source_path, extracted_text FROM documents "
        "WHERE lesson_id IS NULL AND status='ingested' AND extracted_text IS NOT NULL "
        "ORDER BY id"
    ).fetchall()
    for doc in pending:
        c = classify_document(doc["source_path"], doc["extracted_text"], claude)
        lesson_id = find_or_create_lesson(conn, cfg, c)
        assign_document_to_lesson(conn, doc["id"], lesson_id)
        report.classified += 1
        touched.add(lesson_id)

    report.lessons_touched = len(touched)
    for lesson_id in touched:
        if synthesize_lesson(conn, cfg, claude, lesson_id) is not None:
            report.synthesized += 1
    return report
