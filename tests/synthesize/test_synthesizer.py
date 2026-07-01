from pathlib import Path
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.classify.types import Classification
from ai_tutor.kb.store import find_or_create_lesson, assign_document_to_lesson
from ai_tutor.synthesize.synthesizer import synthesize_lesson, compute_source_hash


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"GEMINI_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


class FakeClaude:
    def __init__(self): self.calls = 0
    def complete(self, system, user, *, smart=False, max_tokens=1024):
        self.calls += 1
        return "# Bài 5 - Bảng nhân 6\n## Tóm tắt lý thuyết\n6 x n ..."


def _add_doc(conn, h, text):
    conn.execute("INSERT INTO documents(content_hash, source_path, file_type, status, extracted_text) "
                 "VALUES(?,?,?,?,?)", (h, f"{h}.txt", "text", "ingested", text))
    conn.commit()
    return conn.execute("SELECT id FROM documents WHERE content_hash=?", (h,)).fetchone()["id"]


def _lesson_with_doc(conn, cfg):
    c = Classification(lop=3, mon="toan", chuong="Chương 2", bai="Bài 5", ky_nang=(), source="heuristic")
    lid = find_or_create_lesson(conn, cfg, c)
    did = _add_doc(conn, "h1", "Cô dạy bảng nhân 6")
    assign_document_to_lesson(conn, did, lid)
    return lid


def test_synthesize_writes_lesson_md_and_caches(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    lid = _lesson_with_doc(conn, cfg)
    claude = FakeClaude()

    path = synthesize_lesson(conn, cfg, claude, lid)
    assert path is not None and path.name == "lesson.md"
    assert "Bảng nhân 6" in path.read_text(encoding="utf-8")
    assert (path.parent / "meta.json").exists()
    assert claude.calls == 1
    # documents chuyển sang synthesized
    st = conn.execute("SELECT status FROM documents WHERE lesson_id=?", (lid,)).fetchone()["status"]
    assert st == "synthesized"

    # Gọi lại: nguồn không đổi → cache, KHÔNG gọi Claude
    again = synthesize_lesson(conn, cfg, claude, lid)
    assert again is None
    assert claude.calls == 1  # không tăng


def test_source_hash_changes_when_new_doc_added(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    lid = _lesson_with_doc(conn, cfg)
    h_before = compute_source_hash(conn, lid)
    did = _add_doc(conn, "h2", "thêm tài liệu mới")
    assign_document_to_lesson(conn, did, lid)
    assert compute_source_hash(conn, lid) != h_before
