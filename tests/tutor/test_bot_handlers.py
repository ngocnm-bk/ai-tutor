import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.tutor.bot import register_handler, question_handler
from ai_tutor.tutor.students import get_student


def _ctx(tmp_path, args=None, claude=None):
    cfg = load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})
    conn = connect(cfg.db_path); init_db(conn)
    return SimpleNamespace(args=args or [],
                           bot_data={"cfg": cfg, "conn": conn, "claude": claude}), cfg, conn


def _update(text="2+2?", uid=111, name="Bi"):
    sent = AsyncMock()
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=uid, first_name=name),
        message=SimpleNamespace(text=text, reply_text=sent)), sent


def test_register_handler_saves_student(tmp_path):
    ctx, cfg, conn = _ctx(tmp_path, args=["3"])
    update, sent = _update()
    asyncio.run(register_handler(update, ctx))
    assert get_student(conn, 111)["lop"] == 3
    sent.assert_awaited_once()


def test_register_handler_rejects_bad_arg(tmp_path):
    ctx, cfg, conn = _ctx(tmp_path, args=["9"])
    update, sent = _update()
    asyncio.run(register_handler(update, ctx))
    assert get_student(conn, 111) is None
    sent.assert_awaited_once()


def test_question_handler_replies_with_answer(tmp_path):
    class FakeClaude:
        def complete(self, system, user, *, smart=False, max_tokens=1024):
            return "Đáp án nè"
    ctx, cfg, conn = _ctx(tmp_path, claude=FakeClaude())
    # đăng ký + có 1 bài khớp
    from ai_tutor.tutor.students import register_student
    register_student(conn, 111, "Bi", 3)
    d = cfg.kb_dir / "toan" / "lop3" / "chuong-2" / "bai-5"; d.mkdir(parents=True)
    (d / "lesson.md").write_text("Bảng nhân 6", encoding="utf-8")
    conn.execute("INSERT INTO lessons(mon, lop, chuong, bai, dir_path) VALUES('toan',3,'chuong-2','bai-5',?)",
                 (str(d),)); conn.commit()
    update, sent = _update(text="bảng nhân 6")
    asyncio.run(question_handler(update, ctx))
    sent.assert_awaited_once_with("Đáp án nè")
