from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.kb.build import build_kb


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"GEMINI_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


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


class FakeClaudeUnclassifiable(FakeClaude):
    """complete_json trả {} (như _loads_lenient khi Claude output không parse
    được) — mô phỏng trường hợp phân loại bằng Claude thất bại."""
    def complete_json(self, **kw):
        return {}


def test_build_kb_skips_document_that_fails_classification(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    # doc1: heuristic lẫn Claude đều không phân loại được -> phải bị SKIP,
    # không được làm sập build_kb, không tính vào classified.
    _doc(conn, "h1", "ghichu.txt", "nội dung mơ hồ")
    # doc2: heuristic đủ chắc -> vẫn phải được classify + synthesize bình thường
    # dù doc1 thất bại trong cùng 1 lượt build.
    _doc(conn, "h2", "toan-lop3.txt", "Chương 2 Bài 5 bảng nhân 6")

    report = build_kb(cfg, conn, FakeClaudeUnclassifiable())

    assert report.classified == 1
    assert report.lessons_touched == 1
    assert report.synthesized == 1

    rows = conn.execute("SELECT source_path, status FROM documents ORDER BY source_path").fetchall()
    statuses = {r["source_path"]: r["status"] for r in rows}
    assert statuses["ghichu.txt"] == "ingested"  # bỏ qua, giữ nguyên để thử lại sau
    assert statuses["toan-lop3.txt"] == "synthesized"
