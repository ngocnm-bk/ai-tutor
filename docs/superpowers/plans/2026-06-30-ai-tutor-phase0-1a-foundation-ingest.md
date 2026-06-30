# AI Tutor — Phase 0 (Foundation) + Phase 1A (Ingest) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng nền tảng dự án (config, SQLite, Claude client, Telegram echo bot) và pipeline Ingest đưa file từ `inbox/` thành bản ghi `documents` + text đã trích, làm nền cho Classify/Synthesize/Tutor ở các plan sau.

**Architecture:** Python package `ai_tutor` cấu trúc theo trách nhiệm (config/db/claude_client ở gốc; `ingest/` chứa router + processors + pipeline). Mỗi processor là một hàm thuần nhận `Path` trả `str`. Pipeline cô lập lỗi (file hỏng không chặn file khác) và idempotent (băm nội dung chống trùng). Mọi xử lý nặng chạy cục bộ; Claude chỉ gọi khi OCR ảnh kém.

**Tech Stack:** Python 3.11+, `python-telegram-bot`, `anthropic`, `pypdf`, `python-docx`, `pytesseract` (OCR cục bộ), `faster-whisper` + ffmpeg, `pytest`, SQLite (stdlib).

## Global Constraints

- Python **3.11+**.
- **Local-first:** chỉ Anthropic (Claude) là dịch vụ trả phí; mọi thứ khác chạy cục bộ.
- **Tiết kiệm token (bắt buộc):** ưu tiên Python; chỉ gọi Claude khi thật cần; khi gọi thì cắt gọn input, đặt `max_tokens`, dùng model rẻ cho việc đơn giản.
- **Ảnh:** OCR cục bộ (`pytesseract`) trước; chỉ gọi **Claude vision** khi OCR cục bộ ra quá ít text (ngưỡng < 20 ký tự hữu ích).
- **Mock Claude API trong mọi unit test** — không gọi mạng. Inject client để test.
- **ffmpeg** phải có sẵn trên máy (dùng cho video).
- KB tổ chức theo **chương/bài/kỹ năng**, không theo ngày (áp dụng từ plan sau).
- Giao diện là **Telegram** (không Zalo).
- Model: việc đơn giản dùng `claude-haiku-4-5-20251001`; lập luận dạy học (plan sau) dùng `claude-sonnet-4-6`.
- Mã, tên hàm, comment: tiếng Anh cho định danh code; chuỗi hiển thị cho người dùng bằng tiếng Việt.

## File Structure (tạo mới trong plan này)

```
ai-tutor/
  pyproject.toml                     # metadata + deps + pytest config
  .gitignore                         # .venv, .env, data/, __pycache__
  .env.example                       # ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN
  src/ai_tutor/
    __init__.py
    config.py                        # Config dataclass + load_config()
    db.py                            # connect() + init_db() + schema
    claude_client.py                 # ClaudeClient wrapper (inject anthropic client)
    ingest/
      __init__.py
      hashing.py                     # file_content_hash()
      router.py                      # detect_type()
      processors/
        __init__.py
        text_processor.py            # extract_text(path)
        pdf_processor.py             # extract_text(path)
        docx_processor.py            # extract_text(path)
        image_processor.py           # extract_text(path, *, claude)
        video_processor.py           # extract_text(path, *, transcribe)
      pipeline.py                    # ingest_once() + IngestReport
    tutor/
      __init__.py
      bot.py                         # build_application() + echo handler (Phase 0)
  scripts/
    run_bot.py                       # chạy Telegram bot
    ingest_once.py                   # quét inbox một lượt
  tests/
    __init__.py
    test_config.py
    test_db.py
    test_claude_client.py
    test_bot_echo.py
    ingest/
      __init__.py
      test_hashing.py
      test_router.py
      test_text_processor.py
      test_pdf_processor.py
      test_docx_processor.py
      test_image_processor.py
      test_video_processor.py
      test_pipeline.py
    fixtures/                        # file mẫu nhỏ cho test
```

---

### Task 1: Project scaffold + pytest chạy được

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `src/ai_tutor/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: package import được dưới tên `ai_tutor`; `pytest` chạy.

- [ ] **Step 1: Tạo `.gitignore`**

```gitignore
.venv/
.env
__pycache__/
*.pyc
data/
inbox/
!inbox/.gitkeep
kb/
.pytest_cache/
```

- [ ] **Step 2: Tạo `pyproject.toml`**

```toml
[project]
name = "ai-tutor"
version = "0.1.0"
description = "AI Tutor cá nhân/gia đình (Telegram + Claude, local-first)"
requires-python = ">=3.11"
dependencies = [
    "python-telegram-bot>=21",
    "anthropic>=0.40",
    "pypdf>=4",
    "python-docx>=1.1",
    "python-dotenv>=1",
]

[project.optional-dependencies]
# Gói xử lý media nặng — chỉ cần khi xử lý ảnh/video THẬT. Test inject fake nên không cần.
media = ["pytesseract>=0.3.10", "Pillow>=10", "faster-whisper>=1.0"]
dev = ["pytest>=8"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 3: Tạo `.env.example`**

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC...
```

- [ ] **Step 4: Tạo package + smoke test**

`src/ai_tutor/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: (file rỗng)

`tests/test_smoke.py`:
```python
import ai_tutor


def test_package_imports():
    assert ai_tutor.__version__ == "0.1.0"
```

- [ ] **Step 5: Cài đặt + chạy test**

Run:
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/test_smoke.py -v
```
Expected: PASS `test_package_imports`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/ai_tutor/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold ai_tutor package + pytest"
```

---

### Task 2: `config.py` — nạp cấu hình & đường dẫn

**Files:**
- Create: `src/ai_tutor/config.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Config` với: `anthropic_api_key: str`, `telegram_bot_token: str`, `root: Path`, `inbox_dir: Path`, `failed_dir: Path`, `kb_dir: Path`, `data_dir: Path`, `db_path: Path`.
  - `load_config(root: Path | None = None, env: Mapping[str, str] | None = None) -> Config` — đọc từ `env` (mặc định `os.environ`), tính path theo `root` (mặc định cwd). Tạo sẵn `inbox_dir`, `failed_dir`, `kb_dir`, `data_dir` nếu chưa có. Raise `ValueError` nếu thiếu key bắt buộc.

- [ ] **Step 1: Viết test thất bại**

`tests/test_config.py`:
```python
from pathlib import Path
import pytest
from ai_tutor.config import load_config


def test_load_config_builds_paths_and_dirs(tmp_path: Path):
    env = {"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"}
    cfg = load_config(root=tmp_path, env=env)
    assert cfg.anthropic_api_key == "k"
    assert cfg.telegram_bot_token == "t"
    assert cfg.inbox_dir == tmp_path / "inbox"
    assert cfg.db_path == tmp_path / "data" / "ai_tutor.db"
    assert cfg.inbox_dir.is_dir()
    assert cfg.failed_dir.is_dir()
    assert cfg.data_dir.is_dir()


def test_load_config_missing_key_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k"})
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: ai_tutor.config`).

- [ ] **Step 3: Viết `src/ai_tutor/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    telegram_bot_token: str
    root: Path
    inbox_dir: Path
    failed_dir: Path
    kb_dir: Path
    data_dir: Path
    db_path: Path


def load_config(root: Path | None = None, env: Mapping[str, str] | None = None) -> Config:
    env = env if env is not None else os.environ
    root = (root or Path.cwd()).resolve()

    try:
        api_key = env["ANTHROPIC_API_KEY"]
        bot_token = env["TELEGRAM_BOT_TOKEN"]
    except KeyError as missing:
        raise ValueError(f"Thiếu biến môi trường bắt buộc: {missing}") from missing

    inbox_dir = root / "inbox"
    failed_dir = inbox_dir / "_failed"
    kb_dir = root / "kb"
    data_dir = root / "data"
    for d in (inbox_dir, failed_dir, kb_dir, data_dir):
        d.mkdir(parents=True, exist_ok=True)

    return Config(
        anthropic_api_key=api_key,
        telegram_bot_token=bot_token,
        root=root,
        inbox_dir=inbox_dir,
        failed_dir=failed_dir,
        kb_dir=kb_dir,
        data_dir=data_dir,
        db_path=data_dir / "ai_tutor.db",
    )
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: PASS cả 2 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/config.py tests/test_config.py
git commit -m "feat(config): load_config với path + kiểm tra env"
```

---

### Task 3: `db.py` — SQLite schema & khởi tạo

**Files:**
- Create: `src/ai_tutor/db.py`, `tests/test_db.py`

**Interfaces:**
- Produces:
  - `connect(db_path: Path) -> sqlite3.Connection` — bật `row_factory = sqlite3.Row` và `PRAGMA foreign_keys = ON`.
  - `init_db(conn: sqlite3.Connection) -> None` — tạo (idempotent) các bảng: `documents`, `lessons`, `skills`, `lesson_skills`, `students`, `qa_log`. Cột `documents.content_hash` UNIQUE.

- [ ] **Step 1: Viết test thất bại**

`tests/test_db.py`:
```python
from pathlib import Path
import sqlite3
import pytest
from ai_tutor.db import connect, init_db


def test_init_db_creates_tables(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"documents", "lessons", "skills",
            "lesson_skills", "students", "qa_log"} <= names


def test_init_db_is_idempotent(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    init_db(conn)
    init_db(conn)  # không được lỗi


def test_documents_content_hash_unique(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    init_db(conn)
    conn.execute("INSERT INTO documents(content_hash, source_path, file_type, status) "
                 "VALUES('h1','a.txt','text','ingested')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO documents(content_hash, source_path, file_type, status) "
                     "VALUES('h1','b.txt','text','ingested')")
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/test_db.py -v`
Expected: FAIL (`ModuleNotFoundError: ai_tutor.db`).

- [ ] **Step 3: Viết `src/ai_tutor/db.py`**

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY,
    content_hash  TEXT NOT NULL UNIQUE,
    source_path   TEXT NOT NULL,
    file_type     TEXT NOT NULL,
    status        TEXT NOT NULL,
    extracted_text TEXT,
    lesson_id     INTEGER REFERENCES lessons(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lessons (
    id          INTEGER PRIMARY KEY,
    mon         TEXT NOT NULL,
    lop         INTEGER NOT NULL,
    chuong      TEXT,
    bai         TEXT,
    dir_path    TEXT NOT NULL UNIQUE,
    source_hash TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skills (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lesson_skills (
    lesson_id INTEGER NOT NULL REFERENCES lessons(id),
    skill_id  INTEGER NOT NULL REFERENCES skills(id),
    PRIMARY KEY (lesson_id, skill_id)
);

CREATE TABLE IF NOT EXISTS students (
    telegram_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    lop         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_log (
    id          INTEGER PRIMARY KEY,
    telegram_id INTEGER NOT NULL,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    lesson_id   INTEGER REFERENCES lessons(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/test_db.py -v`
Expected: PASS cả 3 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/db.py tests/test_db.py
git commit -m "feat(db): SQLite schema + init_db idempotent"
```

---

### Task 4: `claude_client.py` — wrapper tiết kiệm token, inject được để test

**Files:**
- Create: `src/ai_tutor/claude_client.py`, `tests/test_claude_client.py`

**Interfaces:**
- Produces:
  - `class ClaudeClient` khởi tạo `ClaudeClient(client, *, cheap_model="claude-haiku-4-5-20251001", smart_model="claude-sonnet-4-6")` — `client` là đối tượng kiểu `anthropic.Anthropic` (inject để mock).
  - `ClaudeClient.complete(system: str, user: str, *, smart: bool = False, max_tokens: int = 1024) -> str` — gọi `messages.create`, chọn model theo `smart`, trả text gộp từ các block `type == "text"`.
  - `classmethod ClaudeClient.from_config(cfg) -> ClaudeClient` — tạo `anthropic.Anthropic(api_key=cfg.anthropic_api_key)` thật.

- [ ] **Step 1: Viết test thất bại (mock client)**

`tests/test_claude_client.py`:
```python
from types import SimpleNamespace
from ai_tutor.claude_client import ClaudeClient


class FakeMessages:
    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="xin chào")])


class FakeAnthropic:
    def __init__(self):
        self.messages = FakeMessages()


def test_complete_returns_text_and_uses_cheap_model_by_default():
    fake = FakeAnthropic()
    client = ClaudeClient(fake)
    out = client.complete(system="s", user="u")
    assert out == "xin chào"
    assert fake.messages.last_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert fake.messages.last_kwargs["max_tokens"] == 1024


def test_complete_smart_uses_smart_model():
    fake = FakeAnthropic()
    client = ClaudeClient(fake)
    client.complete(system="s", user="u", smart=True, max_tokens=200)
    assert fake.messages.last_kwargs["model"] == "claude-sonnet-4-6"
    assert fake.messages.last_kwargs["max_tokens"] == 200
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/test_claude_client.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết `src/ai_tutor/claude_client.py`**

```python
from __future__ import annotations


class ClaudeClient:
    def __init__(self, client, *, cheap_model="claude-haiku-4-5-20251001",
                 smart_model="claude-sonnet-4-6"):
        self._client = client
        self._cheap_model = cheap_model
        self._smart_model = smart_model

    @classmethod
    def from_config(cls, cfg) -> "ClaudeClient":
        import anthropic
        return cls(anthropic.Anthropic(api_key=cfg.anthropic_api_key))

    def complete(self, system: str, user: str, *, smart: bool = False,
                 max_tokens: int = 1024) -> str:
        model = self._smart_model if smart else self._cheap_model
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/test_claude_client.py -v`
Expected: PASS cả 2 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/claude_client.py tests/test_claude_client.py
git commit -m "feat(claude): ClaudeClient wrapper inject được, chọn model theo độ khó"
```

---

### Task 5: Telegram echo bot (Phase 0 — chạy thật được)

**Files:**
- Create: `src/ai_tutor/tutor/__init__.py`, `src/ai_tutor/tutor/bot.py`, `scripts/run_bot.py`, `tests/test_bot_echo.py`

**Interfaces:**
- Consumes: `Config` từ Task 2.
- Produces:
  - `async echo_handler(update, context) -> None` — trả lại đúng text người dùng gửi, prefix `"Bot: "`.
  - `build_application(cfg: Config)` — tạo `Application` của `python-telegram-bot`, đăng ký `echo_handler` cho message text.

- [ ] **Step 1: Viết test thất bại (mock update/context, không gọi mạng)**

`tests/test_bot_echo.py`:
```python
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from ai_tutor.tutor.bot import echo_handler


def test_echo_handler_replies_with_prefix():
    sent = AsyncMock()
    update = SimpleNamespace(message=SimpleNamespace(text="2+2?", reply_text=sent))
    asyncio.run(echo_handler(update, context=SimpleNamespace()))
    sent.assert_awaited_once_with("Bot: 2+2?")
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/test_bot_echo.py -v`
Expected: FAIL (`ModuleNotFoundError: ai_tutor.tutor.bot`).

- [ ] **Step 3: Viết `src/ai_tutor/tutor/__init__.py` (rỗng) và `bot.py`**

`src/ai_tutor/tutor/bot.py`:
```python
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ai_tutor.config import Config


async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Bot: {update.message.text}")


def build_application(cfg: Config) -> Application:
    app = Application.builder().token(cfg.telegram_bot_token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_handler))
    return app
```

- [ ] **Step 4: Viết `scripts/run_bot.py`**

```python
from dotenv import load_dotenv
from ai_tutor.config import load_config
from ai_tutor.tutor.bot import build_application


def main() -> None:
    load_dotenv()
    cfg = load_config()
    app = build_application(cfg)
    print("AI Tutor bot đang chạy. Nhấn Ctrl+C để dừng.")
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/test_bot_echo.py -v`
Expected: PASS.

- [ ] **Step 6: (Thủ công, tùy chọn) chạy thật**

Tạo `.env` từ `.env.example` với token thật, rồi:
Run: `.venv/Scripts/python scripts/run_bot.py`
Expected: nhắn cho bot trên Telegram → bot trả `"Bot: <tin nhắn>"`.

- [ ] **Step 7: Commit**

```bash
git add src/ai_tutor/tutor/__init__.py src/ai_tutor/tutor/bot.py scripts/run_bot.py tests/test_bot_echo.py
git commit -m "feat(tutor): Telegram echo bot (Phase 0)"
```

---

### Task 6: Ingest — băm chống trùng + nhận diện loại file

**Files:**
- Create: `src/ai_tutor/ingest/__init__.py`, `src/ai_tutor/ingest/hashing.py`, `src/ai_tutor/ingest/router.py`, `tests/ingest/__init__.py`, `tests/ingest/test_hashing.py`, `tests/ingest/test_router.py`

**Interfaces:**
- Produces:
  - `file_content_hash(path: Path) -> str` — SHA-256 hex của nội dung file (đọc theo block).
  - `detect_type(path: Path) -> str` — trả `"text" | "pdf" | "docx" | "image" | "video" | "unknown"` dựa trên đuôi file (lowercase). Ánh xạ: `.txt/.md → text`, `.pdf → pdf`, `.docx → docx`, `.png/.jpg/.jpeg/.webp → image`, `.mp4/.mkv/.mov/.m4a/.mp3 → video`, còn lại `unknown`.

- [ ] **Step 1: Viết test thất bại**

`tests/ingest/__init__.py`: (rỗng)

`tests/ingest/test_hashing.py`:
```python
from ai_tutor.ingest.hashing import file_content_hash


def test_hash_is_stable_and_content_based(tmp_path):
    a = tmp_path / "a.txt"; a.write_text("hello", encoding="utf-8")
    b = tmp_path / "b.txt"; b.write_text("hello", encoding="utf-8")
    c = tmp_path / "c.txt"; c.write_text("world", encoding="utf-8")
    assert file_content_hash(a) == file_content_hash(b)
    assert file_content_hash(a) != file_content_hash(c)
    assert len(file_content_hash(a)) == 64
```

`tests/ingest/test_router.py`:
```python
import pytest
from ai_tutor.ingest.router import detect_type


@pytest.mark.parametrize("name,expected", [
    ("a.txt", "text"), ("a.md", "text"), ("a.PDF", "pdf"),
    ("a.docx", "docx"), ("a.jpg", "image"), ("a.png", "image"),
    ("a.mp4", "video"), ("a.mp3", "video"), ("a.zip", "unknown"),
])
def test_detect_type(tmp_path, name, expected):
    p = tmp_path / name; p.write_bytes(b"x")
    assert detect_type(p) == expected
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_hashing.py tests/ingest/test_router.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/ingest/__init__.py`: (rỗng)

`src/ai_tutor/ingest/hashing.py`:
```python
from __future__ import annotations

import hashlib
from pathlib import Path


def file_content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
```

`src/ai_tutor/ingest/router.py`:
```python
from __future__ import annotations

from pathlib import Path

_EXT_MAP = {
    ".txt": "text", ".md": "text",
    ".pdf": "pdf",
    ".docx": "docx",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
    ".mp4": "video", ".mkv": "video", ".mov": "video", ".m4a": "video", ".mp3": "video",
}


def detect_type(path: Path) -> str:
    return _EXT_MAP.get(path.suffix.lower(), "unknown")
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_hashing.py tests/ingest/test_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/ingest/__init__.py src/ai_tutor/ingest/hashing.py src/ai_tutor/ingest/router.py tests/ingest/__init__.py tests/ingest/test_hashing.py tests/ingest/test_router.py
git commit -m "feat(ingest): hash chống trùng + detect_type"
```

---

### Task 7: Processor — text & markdown

**Files:**
- Create: `src/ai_tutor/ingest/processors/__init__.py`, `src/ai_tutor/ingest/processors/text_processor.py`, `tests/ingest/test_text_processor.py`

**Interfaces:**
- Produces: `extract_text(path: Path) -> str` — đọc UTF-8, trả nội dung đã `strip()`.

- [ ] **Step 1: Viết test thất bại**

`tests/ingest/test_text_processor.py`:
```python
from ai_tutor.ingest.processors.text_processor import extract_text


def test_extract_text_reads_and_strips(tmp_path):
    p = tmp_path / "n.txt"; p.write_text("  Bài 5: bảng nhân 6  \n", encoding="utf-8")
    assert extract_text(p) == "Bài 5: bảng nhân 6"
```

- [ ] **Step 2: Chạy FAIL**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_text_processor.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/ingest/processors/__init__.py`: (rỗng)

`src/ai_tutor/ingest/processors/text_processor.py`:
```python
from __future__ import annotations

from pathlib import Path


def extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()
```

- [ ] **Step 4: Chạy PASS**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_text_processor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/ingest/processors/__init__.py src/ai_tutor/ingest/processors/text_processor.py tests/ingest/test_text_processor.py
git commit -m "feat(ingest): text/markdown processor"
```

---

### Task 8: Processor — PDF

**Files:**
- Create: `src/ai_tutor/ingest/processors/pdf_processor.py`, `tests/ingest/test_pdf_processor.py`

**Interfaces:**
- Produces: `extract_text(path: Path) -> str` — dùng `pypdf.PdfReader`, nối text các trang bằng `"\n"`, `strip()`.

- [ ] **Step 1: Viết test thất bại (tạo PDF mẫu bằng pypdf)**

`tests/ingest/test_pdf_processor.py`:
```python
import pytest
from ai_tutor.ingest.processors.pdf_processor import extract_text


def _make_pdf_with_text(path, text):
    # pypdf không tạo text trang; dùng reportlab nếu có, ngược lại skip.
    rl = pytest.importorskip("reportlab.pdfgen.canvas")
    c = rl.Canvas(str(path))
    c.drawString(72, 720, text)
    c.save()


def test_extract_text_from_pdf(tmp_path):
    p = tmp_path / "d.pdf"
    _make_pdf_with_text(p, "Chuong 2 phep nhan")
    assert "phep nhan" in extract_text(p).lower()
```

> Ghi chú: nếu `reportlab` chưa có, test tự skip — không chặn pipeline. Thêm `reportlab` vào `dev` deps nếu muốn test chạy thật: `pip install reportlab`.

- [ ] **Step 2: Chạy FAIL**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_pdf_processor.py -v`
Expected: FAIL (`ModuleNotFoundError: ...pdf_processor`) hoặc SKIP nếu thiếu reportlab — cài reportlab để thấy FAIL thật.

- [ ] **Step 3: Viết code**

`src/ai_tutor/ingest/processors/pdf_processor.py`:
```python
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts).strip()
```

- [ ] **Step 4: Chạy PASS**

Run: `.venv/Scripts/python -m pip install reportlab && .venv/Scripts/python -m pytest tests/ingest/test_pdf_processor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/ingest/processors/pdf_processor.py tests/ingest/test_pdf_processor.py
git commit -m "feat(ingest): pdf processor (pypdf)"
```

---

### Task 9: Processor — DOCX

**Files:**
- Create: `src/ai_tutor/ingest/processors/docx_processor.py`, `tests/ingest/test_docx_processor.py`

**Interfaces:**
- Produces: `extract_text(path: Path) -> str` — dùng `docx.Document`, nối `paragraph.text` bằng `"\n"`, `strip()`.

- [ ] **Step 1: Viết test thất bại (tạo docx mẫu bằng python-docx)**

`tests/ingest/test_docx_processor.py`:
```python
import docx
from ai_tutor.ingest.processors.docx_processor import extract_text


def test_extract_text_from_docx(tmp_path):
    p = tmp_path / "d.docx"
    doc = docx.Document()
    doc.add_paragraph("Unit 3: Present Simple")
    doc.add_paragraph("Bài tập 1")
    doc.save(str(p))
    out = extract_text(p)
    assert "Present Simple" in out
    assert "Bài tập 1" in out
```

- [ ] **Step 2: Chạy FAIL**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_docx_processor.py -v`
Expected: FAIL (`ModuleNotFoundError: ...docx_processor`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/ingest/processors/docx_processor.py`:
```python
from __future__ import annotations

from pathlib import Path

import docx


def extract_text(path: Path) -> str:
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs).strip()
```

- [ ] **Step 4: Chạy PASS**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_docx_processor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/ingest/processors/docx_processor.py tests/ingest/test_docx_processor.py
git commit -m "feat(ingest): docx processor (python-docx)"
```

---

### Task 10: Processor — ảnh (OCR cục bộ trước, Claude vision khi kém)

**Files:**
- Create: `src/ai_tutor/ingest/processors/image_processor.py`, `tests/ingest/test_image_processor.py`

**Interfaces:**
- Consumes: `ClaudeClient` (Task 4) — nhưng để tiết kiệm token và dễ test, processor nhận **2 callable inject**: `ocr` và `vision`.
- Produces:
  - `extract_text(path: Path, *, ocr: Callable[[Path], str], vision: Callable[[Path], str], min_chars: int = 20) -> str` — chạy `ocr(path)` trước; nếu kết quả `strip()` có ≥ `min_chars` ký tự thì trả luôn (KHÔNG gọi vision); ngược lại gọi `vision(path)`.
  - `default_ocr(path: Path) -> str` — dùng `pytesseract.image_to_string` (lang `vie+eng` nếu có, fallback mặc định).

- [ ] **Step 1: Viết test thất bại (inject fake ocr/vision — không gọi mạng, không cần Tesseract)**

`tests/ingest/test_image_processor.py`:
```python
from pathlib import Path
from ai_tutor.ingest.processors.image_processor import extract_text


def test_uses_local_ocr_when_enough_text(tmp_path):
    img = tmp_path / "a.png"; img.write_bytes(b"x")
    calls = {"vision": 0}

    def ocr(p): return "Bài 5: bảng nhân 6 — đủ dài để dùng được"

    def vision(p):
        calls["vision"] += 1
        return "VISION"

    out = extract_text(img, ocr=ocr, vision=vision)
    assert "bảng nhân 6" in out
    assert calls["vision"] == 0  # KHÔNG gọi Claude


def test_falls_back_to_vision_when_ocr_poor(tmp_path):
    img = tmp_path / "a.png"; img.write_bytes(b"x")

    def ocr(p): return "  ?? "  # quá ít ký tự

    def vision(p): return "Đề bài: 6 x 7 = ?"

    out = extract_text(img, ocr=ocr, vision=vision)
    assert out == "Đề bài: 6 x 7 = ?"
```

- [ ] **Step 2: Chạy FAIL**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_image_processor.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/ingest/processors/image_processor.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Callable


def extract_text(path: Path, *, ocr: Callable[[Path], str],
                 vision: Callable[[Path], str], min_chars: int = 20) -> str:
    local = (ocr(path) or "").strip()
    if len(local) >= min_chars:
        return local
    return (vision(path) or "").strip()


def default_ocr(path: Path) -> str:
    import pytesseract
    from PIL import Image
    img = Image.open(path)
    try:
        return pytesseract.image_to_string(img, lang="vie+eng")
    except pytesseract.TesseractError:
        return pytesseract.image_to_string(img)
```

> Ghi chú: `default_ocr` import `pytesseract`/`PIL` **lazy** (trong hàm) nên test (inject fake) không cần cài `[media]`. `vision` thật được tạo ở Task 12 từ `ClaudeClient`. Ràng buộc token: chỉ gọi khi OCR kém.

- [ ] **Step 4: Chạy PASS**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_image_processor.py -v`
Expected: PASS cả 2 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/ingest/processors/image_processor.py tests/ingest/test_image_processor.py
git commit -m "feat(ingest): image processor — OCR cục bộ trước, vision khi kém"
```

---

### Task 11: Processor — video (ffmpeg + faster-whisper), transcribe inject được

**Files:**
- Create: `src/ai_tutor/ingest/processors/video_processor.py`, `tests/ingest/test_video_processor.py`

**Interfaces:**
- Produces:
  - `extract_text(path: Path, *, transcribe: Callable[[Path], str]) -> str` — gọi `transcribe(path)`, `strip()`. (Tách audio + chạy Whisper nằm trong `transcribe` thật để test không cần ffmpeg.)
  - `default_transcribe(path: Path, *, model_size: str = "small") -> str` — import `faster_whisper` **lazy** (trong hàm); dùng `WhisperModel(model_size)`, `transcribe(str(path))`, nối các segment.text. faster-whisper tự đọc audio từ file media qua ffmpeg. (Cần cài `[media]` + ffmpeg khi chạy thật; test inject fake nên không cần.)

- [ ] **Step 1: Viết test thất bại (inject fake transcribe)**

`tests/ingest/test_video_processor.py`:
```python
from ai_tutor.ingest.processors.video_processor import extract_text


def test_extract_text_uses_injected_transcriber(tmp_path):
    v = tmp_path / "lesson.mp4"; v.write_bytes(b"fakevideo")

    def transcribe(p): return "  Hôm nay cô dạy bảng nhân 6.  "

    assert extract_text(v, transcribe=transcribe) == "Hôm nay cô dạy bảng nhân 6."
```

- [ ] **Step 2: Chạy FAIL**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_video_processor.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/ingest/processors/video_processor.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Callable


def extract_text(path: Path, *, transcribe: Callable[[Path], str]) -> str:
    return (transcribe(path) or "").strip()


def default_transcribe(path: Path, *, model_size: str = "small") -> str:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size)
    segments, _ = model.transcribe(str(path), language="vi")
    return " ".join(seg.text.strip() for seg in segments)
```

- [ ] **Step 4: Chạy PASS**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_video_processor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/ingest/processors/video_processor.py tests/ingest/test_video_processor.py
git commit -m "feat(ingest): video processor — faster-whisper (transcribe inject được)"
```

---

### Task 12: Ingest pipeline — quét inbox, dedupe, lưu documents, cô lập lỗi

**Files:**
- Create: `src/ai_tutor/ingest/pipeline.py`, `scripts/ingest_once.py`, `tests/ingest/test_pipeline.py`

**Interfaces:**
- Consumes: `detect_type` (Task 6), `file_content_hash` (Task 6), các `extract_text` (Task 7–11), `connect/init_db` (Task 3), `Config` (Task 2).
- Produces:
  - `@dataclass IngestReport` với: `ingested: int`, `skipped: int`, `failed: int`, `failed_files: list[str]`.
  - `ingest_once(cfg, conn, *, extractors: dict[str, Callable[[Path], str]]) -> IngestReport` — duyệt mọi file trong `cfg.inbox_dir` (bỏ qua `_failed/` và file ẩn). Với mỗi file: tính hash; nếu hash đã có trong `documents` → `skipped`. Chọn extractor theo `detect_type`; `unknown` hoặc không có extractor → coi là lỗi. Gọi extractor → INSERT `documents(content_hash, source_path, file_type, status='ingested', extracted_text)`. Nếu extractor ném exception → ghi log, **move file sang `cfg.failed_dir`**, tăng `failed`, KHÔNG dừng vòng lặp.
  - `build_default_extractors(claude: ClaudeClient) -> dict[str, Callable[[Path], str]]` — map `text/pdf/docx/image/video` sang các `extract_text` đã bind dependency (vision/ocr/transcribe thật). (Dùng ở `scripts/ingest_once.py`, không cần test mạng.)

- [ ] **Step 1: Viết test thất bại (extractors giả, cô lập lỗi)**

`tests/ingest/test_pipeline.py`:
```python
from pathlib import Path
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.ingest.pipeline import ingest_once


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


def _extractors():
    return {
        "text": lambda p: f"TEXT:{p.read_text(encoding='utf-8')}",
        "pdf": lambda p: "PDF",
        "image": lambda p: (_ for _ in ()).throw(RuntimeError("ocr boom")),
    }


def test_ingest_stores_documents_and_isolates_errors(tmp_path):
    cfg = _cfg(tmp_path)
    (cfg.inbox_dir / "a.txt").write_text("bài 5", encoding="utf-8")
    (cfg.inbox_dir / "b.png").write_bytes(b"img")     # extractor sẽ ném lỗi
    conn = connect(cfg.db_path); init_db(conn)

    report = ingest_once(cfg, conn, extractors=_extractors())

    assert report.ingested == 1
    assert report.failed == 1
    rows = conn.execute("SELECT file_type, extracted_text FROM documents").fetchall()
    assert rows[0]["file_type"] == "text"
    assert "bài 5" in rows[0]["extracted_text"]
    assert not (cfg.inbox_dir / "b.png").exists()           # đã move
    assert (cfg.failed_dir / "b.png").exists()


def test_ingest_skips_duplicate_hash(tmp_path):
    cfg = _cfg(tmp_path)
    (cfg.inbox_dir / "a.txt").write_text("same", encoding="utf-8")
    conn = connect(cfg.db_path); init_db(conn)
    ingest_once(cfg, conn, extractors=_extractors())

    (cfg.inbox_dir / "copy.txt").write_text("same", encoding="utf-8")  # cùng nội dung
    report = ingest_once(cfg, conn, extractors=_extractors())
    assert report.skipped == 1
    assert report.ingested == 0
```

- [ ] **Step 2: Chạy FAIL**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_pipeline.py -v`
Expected: FAIL (`ModuleNotFoundError: ...pipeline`).

- [ ] **Step 3: Viết `src/ai_tutor/ingest/pipeline.py`**

```python
from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ai_tutor.config import Config
from ai_tutor.ingest.hashing import file_content_hash
from ai_tutor.ingest.router import detect_type

Extractor = Callable[[Path], str]


@dataclass
class IngestReport:
    ingested: int = 0
    skipped: int = 0
    failed: int = 0
    failed_files: list[str] = field(default_factory=list)


def _iter_inbox(cfg: Config):
    for p in sorted(cfg.inbox_dir.iterdir()):
        if p.is_dir() or p.name.startswith(".") or p.name == "_failed":
            continue
        yield p


def ingest_once(cfg: Config, conn: sqlite3.Connection, *,
                extractors: dict[str, Extractor]) -> IngestReport:
    report = IngestReport()
    for path in _iter_inbox(cfg):
        try:
            content_hash = file_content_hash(path)
            exists = conn.execute(
                "SELECT 1 FROM documents WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            if exists:
                report.skipped += 1
                continue

            ftype = detect_type(path)
            extractor = extractors.get(ftype)
            if extractor is None:
                raise ValueError(f"Không có extractor cho loại '{ftype}'")

            text = extractor(path)
            conn.execute(
                "INSERT INTO documents(content_hash, source_path, file_type, status, extracted_text) "
                "VALUES (?,?,?,?,?)",
                (content_hash, str(path), ftype, "ingested", text),
            )
            conn.commit()
            report.ingested += 1
        except Exception as exc:  # cô lập lỗi: không chặn file khác
            report.failed += 1
            report.failed_files.append(path.name)
            print(f"[ingest] LỖI {path.name}: {exc}")
            shutil.move(str(path), str(cfg.failed_dir / path.name))
    return report


def build_default_extractors(claude) -> dict[str, Extractor]:
    from ai_tutor.ingest.processors import (
        text_processor, pdf_processor, docx_processor,
        image_processor, video_processor,
    )

    def vision(p: Path) -> str:
        # Token-saving: chỉ chạy khi OCR cục bộ kém (do image_processor quyết định).
        import base64
        data = base64.standard_b64encode(p.read_bytes()).decode()
        media = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        resp = claude._client.messages.create(
            model=claude._cheap_model, max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": media, "data": data}},
                {"type": "text", "text": "Trích toàn bộ chữ/đề bài trong ảnh. Chỉ trả text."},
            ]}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")

    return {
        "text": text_processor.extract_text,
        "pdf": pdf_processor.extract_text,
        "docx": docx_processor.extract_text,
        "image": lambda p: image_processor.extract_text(
            p, ocr=image_processor.default_ocr, vision=vision),
        "video": lambda p: video_processor.extract_text(
            p, transcribe=video_processor.default_transcribe),
    }
```

- [ ] **Step 4: Viết `scripts/ingest_once.py`**

```python
from dotenv import load_dotenv
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.claude_client import ClaudeClient
from ai_tutor.ingest.pipeline import ingest_once, build_default_extractors


def main() -> None:
    load_dotenv()
    cfg = load_config()
    conn = connect(cfg.db_path); init_db(conn)
    claude = ClaudeClient.from_config(cfg)
    report = ingest_once(cfg, conn, extractors=build_default_extractors(claude))
    print(f"Đã nạp: {report.ingested} | Bỏ qua (trùng): {report.skipped} | "
          f"Lỗi: {report.failed} {report.failed_files}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/ingest/test_pipeline.py -v`
Expected: PASS cả 2 test.

- [ ] **Step 6: Chạy toàn bộ test bộ**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tất cả PASS (trừ test PDF skip nếu chưa cài reportlab).

- [ ] **Step 7: Commit**

```bash
git add src/ai_tutor/ingest/pipeline.py scripts/ingest_once.py tests/ingest/test_pipeline.py
git commit -m "feat(ingest): pipeline ingest_once — dedupe + lưu documents + cô lập lỗi"
```

---

## Self-Review (đã thực hiện khi viết plan)

**1. Spec coverage (mục liên quan Phase 0 + 1A):**
- Telegram bot (mục 7) → Task 5 (echo, nền cho Tutor plan sau). ✓
- Ingest mọi loại file (mục 2, 5) → Task 6–12. ✓
- Ảnh OCR cục bộ trước, Claude vision khi kém (mục 2, 1.1) → Task 10 + `build_default_extractors`. ✓
- Video → audio → transcribe (mục 2) → Task 11. ✓
- Idempotent + cô lập lỗi (mục 5) → Task 12. ✓
- SQLite schema (mục 4) → Task 3. ✓
- Local-first, chỉ Claude tốn phí, mock Claude khi test (mục 1.1, 15) → Task 4 + mọi test inject/mocking. ✓
- *Chưa thuộc plan này (sang plan 1B/1C):* Classify, Synthesize, KB store/retrieval, Tutor RAG, qa_log ghi nhận. Đã chừa bảng `lessons/skills/lesson_skills/qa_log` sẵn ở Task 3.

**2. Placeholder scan:** Không có "TBD/TODO/implement later"; mọi step code có code thật. Ghi chú ở Task 8/10/11 chỉ giải thích bối cảnh, không thay code.

**3. Type consistency:** `extract_text(path)` đồng nhất across processors (image/video thêm keyword-only deps); `ingest_once(cfg, conn, *, extractors)` khớp `build_default_extractors`; `ClaudeClient` thuộc tính `_client/_cheap_model` được `vision()` dùng đúng tên đã định nghĩa ở Task 4.

## Execution Handoff

Phase 1B (Classify + Synthesize + KB) và 1C (Tutor RAG) sẽ là plan riêng, viết sau khi plan này chạy xong (bám code thực tế).
