from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.kb.retrieval import find_relevant_lesson, _tokens


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


def _add_lesson(conn, cfg, lop, chuong, bai, body):
    d = cfg.kb_dir / "toan" / f"lop{lop}" / chuong / bai
    d.mkdir(parents=True, exist_ok=True)
    (d / "lesson.md").write_text(body, encoding="utf-8")
    cur = conn.execute("INSERT INTO lessons(mon, lop, chuong, bai, dir_path) VALUES('toan',?,?,?,?)",
                       (lop, chuong, bai, str(d)))
    conn.commit()
    return cur.lastrowid


def test_tokens_normalizes_and_filters():
    t = _tokens("Bảng nhân 6, phép NHÂN!")
    assert "bang" in t and "nhan" in t and "6" in t


def test_finds_best_lesson_by_keyword(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    _add_lesson(conn, cfg, 3, "chuong-2", "bai-5", "Bảng nhân 6: 6x1=6, 6x2=12")
    lid_other = _add_lesson(conn, cfg, 3, "chuong-3", "bai-9", "Phép chia hết")
    hit = find_relevant_lesson(conn, cfg, 3, "con chưa thuộc bảng nhân 6")
    assert hit is not None
    lid, body = hit
    assert "nhân 6" in body and lid != lid_other


def test_returns_none_when_no_match(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    _add_lesson(conn, cfg, 3, "chuong-2", "bai-5", "Bảng nhân 6")
    assert find_relevant_lesson(conn, cfg, 3, "thì hiện tại đơn tiếng anh") is None


def test_respects_lop(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    _add_lesson(conn, cfg, 6, "chuong-1", "bai-1", "Bảng nhân 6")  # lớp 6
    assert find_relevant_lesson(conn, cfg, 3, "bảng nhân 6") is None  # hỏi ở lớp 3
