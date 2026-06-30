from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.tutor.students import register_student
from ai_tutor.tutor.tutor_service import answer_question
from ai_tutor.tutor.prompts import NOT_REGISTERED_REPLY, NO_CONTEXT_REPLY


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


class FakeClaude:
    def __init__(self): self.calls = 0; self.last_system = None
    def complete(self, system, user, *, smart=False, max_tokens=1024):
        self.calls += 1
        self.last_system = system
        return "6 nhân 7 bằng 42 con nhé."


def _add_lesson(conn, cfg, lop, body):
    d = cfg.kb_dir / "toan" / f"lop{lop}" / "chuong-2" / "bai-5"
    d.mkdir(parents=True, exist_ok=True)
    (d / "lesson.md").write_text(body, encoding="utf-8")
    conn.execute("INSERT INTO lessons(mon, lop, chuong, bai, dir_path) VALUES('toan',?,?,?,?)",
                 (lop, "chuong-2", "bai-5", str(d)))
    conn.commit()


def test_unregistered_student_gets_prompt_no_claude(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    claude = FakeClaude()
    out = answer_question(conn, cfg, claude, 111, "Bi", "6x7?")
    assert out == NOT_REGISTERED_REPLY
    assert claude.calls == 0
    assert conn.execute("SELECT COUNT(*) c FROM qa_log").fetchone()["c"] == 0


def test_no_relevant_lesson_fallback_no_claude(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    register_student(conn, 111, "Bi", 3)
    claude = FakeClaude()
    out = answer_question(conn, cfg, claude, 111, "Bi", "thì hiện tại đơn")
    assert out == NO_CONTEXT_REPLY
    assert claude.calls == 0  # tiết kiệm token
    row = conn.execute("SELECT lesson_id, answer FROM qa_log").fetchone()
    assert row is not None and row["lesson_id"] is None
    assert row["answer"] == NO_CONTEXT_REPLY


def test_answers_from_lesson_and_logs(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    register_student(conn, 111, "Bi", 3)
    _add_lesson(conn, cfg, 3, "Bảng nhân 6: 6x7=42")
    claude = FakeClaude()
    out = answer_question(conn, cfg, claude, 111, "Bi", "6 nhân 7 bằng mấy trong bảng nhân 6")
    assert "42" in out
    assert claude.calls == 1
    # grounding: system prompt là build_system_prompt(lop) — ràng buộc "chỉ dựa trên tài liệu"
    from ai_tutor.tutor.prompts import build_system_prompt
    assert claude.last_system == build_system_prompt(3)
    row = conn.execute("SELECT telegram_id, lesson_id, answer FROM qa_log").fetchone()
    assert row["telegram_id"] == 111 and row["lesson_id"] is not None
    assert row["answer"] == out
