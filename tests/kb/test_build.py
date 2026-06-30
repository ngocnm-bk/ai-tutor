from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.kb.build import build_kb


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


class FakeClaude:
    def complete(self, system, user, *, smart=False, max_tokens=1024):
        return "# Bài 5\n## Tóm tắt lý thuyết\nnội dung"
    def complete_json(self, **kw):
        return {"lop": 3, "mon": "toan"}  # chỉ dùng nếu heuristic trượt


def _doc(conn, h, path, text):
    conn.execute("INSERT INTO documents(content_hash, source_path, file_type, status, extracted_text) "
                 "VALUES(?,?,?,?,?)", (h, path, "text", "ingested", text))
    conn.commit()


def test_build_kb_classifies_and_synthesizes(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    # heuristic đủ chắc (path có lop+mon, text có bài)
    _doc(conn, "h1", "toan-lop3.txt", "Chương 2 Bài 5 bảng nhân 6")
    report = build_kb(cfg, conn, FakeClaude())

    assert report.classified == 1
    assert report.lessons_touched == 1
    assert report.synthesized == 1
    # lesson.md được tạo
    assert (cfg.kb_dir / "toan" / "lop3" / "chuong-2" / "bai-5" / "lesson.md").exists()
    # document đã synthesized
    st = conn.execute("SELECT status FROM documents").fetchone()["status"]
    assert st == "synthesized"


def test_build_kb_skips_already_classified(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    _doc(conn, "h1", "toan-lop3.txt", "Chương 2 Bài 5 bảng nhân 6")
    build_kb(cfg, conn, FakeClaude())
    report2 = build_kb(cfg, conn, FakeClaude())  # không còn document 'ingested'
    assert report2.classified == 0
    assert report2.lessons_touched == 0
    assert report2.synthesized == 0
