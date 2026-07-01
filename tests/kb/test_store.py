from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.classify.types import Classification
from ai_tutor.kb.store import find_or_create_lesson, assign_document_to_lesson


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"GEMINI_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


def _c(ky=()):
    return Classification(lop=3, mon="toan", chuong="Chương 2", bai="Bài 5",
                          ky_nang=ky, source="heuristic")


def test_create_then_find_is_idempotent_and_makes_dir(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    lid1 = find_or_create_lesson(conn, cfg, _c(("bang-nhan-6",)))
    lid2 = find_or_create_lesson(conn, cfg, _c(("bang-nhan-6",)))
    assert lid1 == lid2  # cùng dir_path → cùng lesson
    row = conn.execute("SELECT dir_path, mon, lop FROM lessons WHERE id=?", (lid1,)).fetchone()
    assert row["mon"] == "toan" and row["lop"] == 3
    assert (cfg.kb_dir / "toan" / "lop3" / "chuong-2" / "bai-5").is_dir()
    # kỹ năng được lưu + liên kết
    n = conn.execute("SELECT COUNT(*) c FROM lesson_skills WHERE lesson_id=?", (lid1,)).fetchone()["c"]
    assert n == 1


def test_assign_document_sets_lesson_and_status(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    conn.execute("INSERT INTO documents(content_hash, source_path, file_type, status, extracted_text) "
                 "VALUES('h','a.txt','text','ingested','Bài 5')")
    conn.commit()
    doc_id = conn.execute("SELECT id FROM documents").fetchone()["id"]
    lid = find_or_create_lesson(conn, cfg, _c())
    assign_document_to_lesson(conn, doc_id, lid)
    row = conn.execute("SELECT lesson_id, status FROM documents WHERE id=?", (doc_id,)).fetchone()
    assert row["lesson_id"] == lid and row["status"] == "classified"
