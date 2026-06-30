# AI Tutor — Phase 1C (Tutor RAG qua Telegram) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biến echo bot thành **AI Tutor thật**: con nhắn câu hỏi qua Telegram → hệ thống tìm bài liên quan trong KB → Claude trả lời CHỈ dựa trên `lesson.md` của giáo viên, phân biệt 2 con theo lớp, ghi log hỏi/đáp.

**Architecture:** Thêm: đăng ký học sinh (`tutor/students.py`), truy hồi bài theo từ khóa (`kb/retrieval.py` — pure Python, không token), prompt ràng buộc (`tutor/prompts.py`), dịch vụ trả lời (`tutor/tutor_service.py` — student → retrieve → Claude → log). Sửa `tutor/bot.py`: lệnh đăng ký + handler câu hỏi gọi tutor_service. Claude chỉ được gọi khi có bài liên quan (nếu không có → trả lời "chưa có trong tài liệu" bằng Python, không tốn token).

**Tech Stack:** Python 3.11+, `python-telegram-bot`, `anthropic` (Claude Sonnet cho trả lời), SQLite (stdlib). Không thêm dependency mới.

## Global Constraints

- Python **3.11+** (máy chạy 3.14.3). Chạy qua `.venv/Scripts/python` (Windows, Git Bash).
- **Local-first:** chỉ Anthropic (Claude) trả phí.
- **Tiết kiệm token (bắt buộc):** truy hồi (retrieval) bằng Python cục bộ — KHÔNG token. Chỉ gọi Claude khi tìm được bài liên quan; nếu không có bài → trả lời fallback bằng Python (không gọi Claude). Đưa vào prompt chỉ nội dung `lesson.md` của bài đã truy hồi (cắt gọn), `max_tokens` giới hạn. Dùng **Sonnet** (`smart=True`) cho trả lời dạy học.
- **Grounding bắt buộc:** system prompt yêu cầu Claude CHỈ trả lời dựa trên tài liệu được cung cấp; nếu không có trong tài liệu thì nói rõ là chưa có và khuyên hỏi cô. Giải thích theo trình độ lớp của học sinh.
- **Giao diện Telegram** (không Zalo). Phân biệt 2 con qua **Telegram user ID** (bảng `students`).
- **Mock/inject Claude & Telegram trong mọi unit test** — không gọi mạng. Logic thuần (tutor_service) test trực tiếp với fake; handler test bằng AsyncMock.
- Định danh code tiếng Anh; chuỗi hiển thị cho con bằng tiếng Việt.

## Bối cảnh code đã có (Phase 0 + 1A + 1B)

- `ai_tutor.config.Config` (kb_dir, db_path, ...), `load_config`.
- `ai_tutor.db`: `connect`, `init_db`. Bảng `students(telegram_id PK, name, lop)`, `qa_log(id, telegram_id, question, answer, lesson_id, created_at)`, `lessons(id, mon, lop, chuong, bai, dir_path, source_hash, ...)`.
- `ai_tutor.claude_client.ClaudeClient.complete(system, user, *, smart=False, max_tokens=1024) -> str`.
- `ai_tutor.tutor.bot`: `echo_handler`, `build_application(cfg)` (hiện đăng ký echo cho text). `scripts/run_bot.py` gọi `build_application` + `run_polling`.
- KB: mỗi bài có thư mục `lessons.dir_path` chứa `lesson.md` (đã tổng hợp ở Phase 1B).

## File Structure (Phase 1C)

```
src/ai_tutor/
  tutor/
    students.py          # register_student, get_student
    prompts.py           # build_system_prompt + chuỗi fallback
    tutor_service.py     # answer_question (student → retrieve → Claude → log)
    bot.py               # MODIFY: lệnh /dangky + handler câu hỏi (bỏ echo)
  kb/
    retrieval.py         # find_relevant_lesson (keyword, pure Python)
scripts/
  run_bot.py             # MODIFY: nạp conn/cfg/claude vào bot_data
tests/
  tutor/
    __init__.py
    test_students.py
    test_prompts.py
    test_tutor_service.py
    test_bot_handlers.py
  kb/
    test_retrieval.py
```

---

### Task 1: Đăng ký học sinh — students.py

**Files:**
- Create: `src/ai_tutor/tutor/students.py`, `tests/tutor/__init__.py` (rỗng), `tests/tutor/test_students.py`

**Interfaces:**
- Consumes: `connect/init_db`, bảng `students`.
- Produces:
  - `register_student(conn, telegram_id: int, name: str, lop: int) -> None` — `INSERT OR REPLACE INTO students(telegram_id, name, lop)`, commit.
  - `get_student(conn, telegram_id: int) -> sqlite3.Row | None` — `SELECT telegram_id, name, lop FROM students WHERE telegram_id=?`.

- [ ] **Step 1: Viết test thất bại**

`tests/tutor/__init__.py`: (rỗng)

`tests/tutor/test_students.py`:
```python
from ai_tutor.db import connect, init_db
from ai_tutor.tutor.students import register_student, get_student


def _conn(tmp_path):
    c = connect(tmp_path / "t.db"); init_db(c); return c


def test_register_then_get(tmp_path):
    conn = _conn(tmp_path)
    assert get_student(conn, 111) is None
    register_student(conn, 111, "Bi", 3)
    row = get_student(conn, 111)
    assert row["name"] == "Bi" and row["lop"] == 3


def test_register_is_upsert(tmp_path):
    conn = _conn(tmp_path)
    register_student(conn, 111, "Bi", 3)
    register_student(conn, 111, "Bi", 6)  # đổi lớp
    assert get_student(conn, 111)["lop"] == 6
    n = conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]
    assert n == 1
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/tutor/test_students.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/tutor/students.py`:
```python
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
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/tutor/test_students.py -v`
Expected: PASS cả 2 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/tutor/students.py tests/tutor/__init__.py tests/tutor/test_students.py
git commit -m "feat(tutor): đăng ký học sinh (register_student/get_student)"
```

---

### Task 2: Truy hồi bài theo từ khóa — kb/retrieval.py (pure Python, không token)

**Files:**
- Create: `src/ai_tutor/kb/retrieval.py`, `tests/kb/test_retrieval.py`

**Interfaces:**
- Consumes: `Config`, bảng `lessons`, file `lesson.md` trong `dir_path`.
- Produces:
  - `_tokens(s: str) -> set[str]` — bỏ dấu tiếng Việt + lowercase, tách theo ký tự không phải `[a-z0-9]`, bỏ token rỗng và token độ dài < 2.
  - `find_relevant_lesson(conn, cfg, lop: int, question: str) -> tuple[int, str] | None` — lọc `lessons` theo `lop`; với mỗi bài, đọc `lesson.md` (nếu tồn tại trong `dir_path`); chấm điểm = số token câu hỏi xuất hiện trong văn bản `(chuong + bai + lesson.md)`; trả `(lesson_id, lesson_md_text)` của bài điểm cao nhất nếu điểm > 0, ngược lại `None`.

- [ ] **Step 1: Viết test thất bại**

`tests/kb/test_retrieval.py`:
```python
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
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/kb/test_retrieval.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/kb/retrieval.py`:
```python
from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path

from ai_tutor.config import Config


def _tokens(s: str) -> set[str]:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return {t for t in re.split(r"[^a-z0-9]+", s) if len(t) >= 2}


def find_relevant_lesson(conn: sqlite3.Connection, cfg: Config, lop: int,
                         question: str) -> tuple[int, str] | None:
    q_tokens = _tokens(question)
    if not q_tokens:
        return None
    best_id: int | None = None
    best_body = ""
    best_score = 0
    rows = conn.execute(
        "SELECT id, chuong, bai, dir_path FROM lessons WHERE lop=?", (lop,)
    ).fetchall()
    for row in rows:
        md_path = Path(row["dir_path"]) / "lesson.md"
        body = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        haystack = _tokens(f"{row['chuong'] or ''} {row['bai'] or ''} {body}")
        score = len(q_tokens & haystack)
        if score > best_score:
            best_score, best_id, best_body = score, row["id"], body
    if best_id is None:
        return None
    return best_id, best_body
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/kb/test_retrieval.py -v`
Expected: PASS cả 4 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/kb/retrieval.py tests/kb/test_retrieval.py
git commit -m "feat(kb): find_relevant_lesson — truy hồi từ khóa (pure Python)"
```

---

### Task 3: Prompt ràng buộc + chuỗi fallback — tutor/prompts.py

**Files:**
- Create: `src/ai_tutor/tutor/prompts.py`, `tests/tutor/test_prompts.py`

**Interfaces:**
- Produces:
  - `build_system_prompt(lop: int) -> str` — system prompt yêu cầu Claude CHỈ dựa trên tài liệu, nếu không có thì nói chưa có và khuyên hỏi cô, giải thích theo trình độ `lop`. Chuỗi phải chứa `str(lop)`.
  - `NOT_REGISTERED_REPLY: str` — nhắc đăng ký bằng `/dangky`.
  - `NO_CONTEXT_REPLY: str` — câu trả lời khi không tìm thấy bài liên quan (không gọi Claude).

- [ ] **Step 1: Viết test thất bại**

`tests/tutor/test_prompts.py`:
```python
from ai_tutor.tutor.prompts import build_system_prompt, NOT_REGISTERED_REPLY, NO_CONTEXT_REPLY


def test_system_prompt_grounding_and_lop():
    p = build_system_prompt(3)
    assert "3" in p
    low = p.lower()
    assert "tài liệu" in low  # ràng buộc grounding
    assert "cô" in low        # khuyên hỏi cô khi thiếu


def test_fallback_strings_nonempty():
    assert "dangky" in NOT_REGISTERED_REPLY.lower()
    assert len(NO_CONTEXT_REPLY) > 0
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/tutor/test_prompts.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/tutor/prompts.py`:
```python
from __future__ import annotations

NOT_REGISTERED_REPLY = (
    "Chào con! Trước tiên hãy đăng ký lớp nhé: gõ /dangky 3 hoặc /dangky 6."
)

NO_CONTEXT_REPLY = (
    "Câu này cô chưa có trong tài liệu đã học. Con hỏi lại cô giáo để được "
    "hướng dẫn thêm nhé!"
)


def build_system_prompt(lop: int) -> str:
    return (
        f"Bạn là gia sư cho học sinh lớp {lop}. CHỈ trả lời dựa trên TÀI LIỆU "
        "của cô giáo được cung cấp bên dưới. Nếu câu hỏi không có trong tài liệu, "
        "hãy nói rõ là chưa có trong tài liệu và khuyên con hỏi lại cô giáo — "
        "TUYỆT ĐỐI không bịa thêm. Giải thích ngắn gọn, dễ hiểu, đúng trình độ "
        f"lớp {lop}, bằng tiếng Việt."
    )
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/tutor/test_prompts.py -v`
Expected: PASS cả 2 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/tutor/prompts.py tests/tutor/test_prompts.py
git commit -m "feat(tutor): prompt ràng buộc grounding + chuỗi fallback"
```

---

### Task 4: Dịch vụ trả lời — tutor/tutor_service.py

**Files:**
- Create: `src/ai_tutor/tutor/tutor_service.py`, `tests/tutor/test_tutor_service.py`

**Interfaces:**
- Consumes: `get_student` (Task 1), `find_relevant_lesson` (Task 2), `build_system_prompt`/`NOT_REGISTERED_REPLY`/`NO_CONTEXT_REPLY` (Task 3), `ClaudeClient.complete`, bảng `qa_log`.
- Produces:
  - `answer_question(conn, cfg, claude, telegram_id: int, name: str, question: str) -> str`:
    1. `student = get_student(conn, telegram_id)`. Nếu `None` → trả `NOT_REGISTERED_REPLY` (KHÔNG gọi Claude, KHÔNG ghi log).
    2. `hit = find_relevant_lesson(conn, cfg, student["lop"], question)`. Nếu `None` → `answer = NO_CONTEXT_REPLY` (KHÔNG gọi Claude); ghi `qa_log` với `lesson_id=NULL`; trả `answer`.
    3. Ngược lại: `lesson_id, context = hit`; gọi `claude.complete(build_system_prompt(student["lop"]), f"Câu hỏi: {question}\n\n--- TÀI LIỆU ---\n{context[:8000]}", smart=True, max_tokens=800)`; ghi `qa_log` với `lesson_id`; trả `answer`.
  - `_log_qa(conn, telegram_id, question, answer, lesson_id)` (nội bộ) — INSERT vào `qa_log`, commit.

- [ ] **Step 1: Viết test thất bại (fake claude đếm số lần gọi)**

`tests/tutor/test_tutor_service.py`:
```python
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.tutor.students import register_student
from ai_tutor.tutor.tutor_service import answer_question
from ai_tutor.tutor.prompts import NOT_REGISTERED_REPLY, NO_CONTEXT_REPLY


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


class FakeClaude:
    def __init__(self): self.calls = 0
    def complete(self, system, user, *, smart=False, max_tokens=1024):
        self.calls += 1
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
    row = conn.execute("SELECT lesson_id FROM qa_log").fetchone()
    assert row is not None and row["lesson_id"] is None


def test_answers_from_lesson_and_logs(tmp_path):
    cfg = _cfg(tmp_path); conn = connect(cfg.db_path); init_db(conn)
    register_student(conn, 111, "Bi", 3)
    _add_lesson(conn, cfg, 3, "Bảng nhân 6: 6x7=42")
    claude = FakeClaude()
    out = answer_question(conn, cfg, claude, 111, "Bi", "6 nhân 7 bằng mấy trong bảng nhân 6")
    assert "42" in out
    assert claude.calls == 1
    row = conn.execute("SELECT telegram_id, lesson_id, answer FROM qa_log").fetchone()
    assert row["telegram_id"] == 111 and row["lesson_id"] is not None
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/tutor/test_tutor_service.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/tutor/tutor_service.py`:
```python
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
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/tutor/test_tutor_service.py -v`
Expected: PASS cả 3 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/tutor/tutor_service.py tests/tutor/test_tutor_service.py
git commit -m "feat(tutor): answer_question — student → retrieve → Claude → log"
```

---

### Task 5: Bot wiring — lệnh /dangky + handler câu hỏi (bỏ echo)

**Files:**
- Modify: `src/ai_tutor/tutor/bot.py`, `scripts/run_bot.py`
- Test: `tests/tutor/test_bot_handlers.py`
- Modify: `tests/test_bot_echo.py` (xóa — echo bị thay; xem Step 1)

**Interfaces:**
- Consumes: `answer_question` (Task 4), `register_student` (Task 1), `Config`, `connect/init_db`, `ClaudeClient`.
- Produces:
  - `async start_handler(update, context) -> None` — trả lời lời chào + hướng dẫn `/dangky 3` hoặc `/dangky 6`.
  - `async register_handler(update, context) -> None` — đọc `context.args`; nếu `args[0]` không thuộc `{"3","6"}` → nhắc cú pháp; ngược lại `register_student(context.bot_data["conn"], user.id, user.first_name, int(args[0]))` rồi xác nhận.
  - `async question_handler(update, context) -> None` — `answer = answer_question(context.bot_data["conn"], context.bot_data["cfg"], context.bot_data["claude"], user.id, user.first_name, update.message.text)`; `reply_text(answer)`.
  - `build_application(cfg, conn, claude)` — tạo `Application`, nạp `bot_data = {"cfg", "conn", "claude"}`, đăng ký `CommandHandler("start", start_handler)`, `CommandHandler("dangky", register_handler)`, `MessageHandler(TEXT & ~COMMAND, question_handler)`. (Đổi chữ ký so với Phase 0: thêm `conn`, `claude`.)

- [ ] **Step 1: Xóa test echo cũ, viết test handler mới**

Xóa file `tests/test_bot_echo.py` (echo_handler bị thay thế):
```bash
git rm tests/test_bot_echo.py
```

`tests/tutor/test_bot_handlers.py`:
```python
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
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/tutor/test_bot_handlers.py -v`
Expected: FAIL (`ImportError: cannot import name 'register_handler'`).

- [ ] **Step 3: Viết `src/ai_tutor/tutor/bot.py` (thay nội dung cũ)**

```python
from __future__ import annotations

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

from ai_tutor.config import Config
from ai_tutor.tutor.students import register_student
from ai_tutor.tutor.tutor_service import answer_question


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Chào con! Đây là gia sư AI. Hãy đăng ký lớp trước: /dangky 3 hoặc /dangky 6. "
        "Sau đó con cứ nhắn câu hỏi về bài học nhé."
    )


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0] not in ("3", "6"):
        await update.message.reply_text("Cú pháp: /dangky 3  hoặc  /dangky 6")
        return
    user = update.effective_user
    register_student(context.bot_data["conn"], user.id, user.first_name, int(args[0]))
    await update.message.reply_text(f"Đã đăng ký {user.first_name} lớp {args[0]}. Con hỏi bài được rồi nhé!")


async def question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    answer = answer_question(
        context.bot_data["conn"], context.bot_data["cfg"], context.bot_data["claude"],
        user.id, user.first_name, update.message.text,
    )
    await update.message.reply_text(answer)


def build_application(cfg: Config, conn, claude) -> Application:
    app = Application.builder().token(cfg.telegram_bot_token).build()
    app.bot_data["cfg"] = cfg
    app.bot_data["conn"] = conn
    app.bot_data["claude"] = claude
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("dangky", register_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, question_handler))
    return app
```

- [ ] **Step 4: Sửa `scripts/run_bot.py`**

```python
from dotenv import load_dotenv
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.claude_client import ClaudeClient
from ai_tutor.tutor.bot import build_application


def main() -> None:
    load_dotenv()
    cfg = load_config()
    conn = connect(cfg.db_path); init_db(conn)
    claude = ClaudeClient.from_config(cfg)
    app = build_application(cfg, conn, claude)
    print("AI Tutor bot đang chạy. Nhấn Ctrl+C để dừng.")
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Chạy test handler — PASS, rồi chạy toàn bộ suite**

Run: `.venv/Scripts/python -m pytest tests/tutor/test_bot_handlers.py -v`
Expected: PASS cả 3 test.
Run: `.venv/Scripts/python -m pytest -q`
Expected: toàn bộ PASS (Phase 0/1A/1B + 1C; test echo cũ đã xóa).

- [ ] **Step 6: Commit**

```bash
git add src/ai_tutor/tutor/bot.py scripts/run_bot.py tests/tutor/test_bot_handlers.py
git commit -m "feat(tutor): bot RAG — /dangky + handler câu hỏi (thay echo)"
```

---

## Self-Review

**1. Spec coverage:**
- AI Tutor Telegram, grounding "chỉ dựa trên tài liệu", giải thích theo lớp, phân biệt 2 con qua telegram_id, ghi qa_log (spec §7) → Task 3 (prompt) + Task 4 (service) + Task 5 (bot) + Task 1 (students). ✓
- Truy hồi Phase 1 bằng từ khóa (spec §8) → Task 2. ✓
- Tiết kiệm token: retrieval Python; Claude chỉ gọi khi có bài; fallback Python khi không có (spec §1.1) → Task 4. ✓
- Học thích ứng / spaced repetition / báo cáo phụ huynh → Phase 3, KHÔNG thuộc plan này. ✓
- Hỏi bài bằng ẢNH (spec §7) → CHỦ Ý hoãn sang sau (1C chỉ làm câu hỏi dạng chữ); ghi nhận ở "Tiếp theo". (Không phải gap của mục tiêu 1C "trả lời câu hỏi chữ".)

**2. Placeholder scan:** Không có "TBD/TODO"; mọi step code có code thật.

**3. Type consistency:** `get_student(conn, telegram_id) -> Row|None` (Task 1) khớp dùng ở Task 4. `find_relevant_lesson(conn, cfg, lop, question) -> tuple[int,str]|None` (Task 2) khớp Task 4. `build_system_prompt(lop)` + `NOT_REGISTERED_REPLY`/`NO_CONTEXT_REPLY` (Task 3) khớp Task 4. `answer_question(conn, cfg, claude, telegram_id, name, question) -> str` (Task 4) khớp `question_handler` (Task 5). `build_application(cfg, conn, claude)` (Task 5) khớp `run_bot.py`. Handler dùng `context.bot_data["conn"|"cfg"|"claude"]` nhất quán với `build_application` nạp `bot_data`.

## Execution Handoff

Sau Phase 1C, hệ thống "dùng thật" được: con đăng ký lớp, nhắn câu hỏi, nhận giải thích theo tài liệu của cô. Phase tiếp theo (2: RAG vector; 3: học thích ứng + báo cáo phụ huynh; hỏi bài bằng ảnh) sẽ là plan riêng.
