# AI Tutor — Phase 1B (Classify + Synthesize + Knowledge Base) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biến các bản ghi `documents` (text đã trích ở Phase 1A) thành Knowledge Base có cấu trúc theo chương/bài: phân loại tài liệu (heuristic Python trước, Claude khi cần), gom vào bài học trong `kb/`, và tổng hợp `lesson.md` (1 lần/bài, có cache).

**Architecture:** Thêm 3 khối vào package `ai_tutor`: `classify/` (heuristic + Claude structured output), `kb/` (paths + store), `synthesize/` (tổng hợp lesson.md). Một orchestrator `kb/build.py` (`build_kb`) duyệt document chưa phân loại → classify → gom vào lesson → synthesize lesson nào có nguồn thay đổi. CLI `scripts/build_kb.py`. Tất cả truy hồi/băm/heuristic chạy Python cục bộ; Claude chỉ gọi khi heuristic không chắc (Haiku) và khi tổng hợp bài (Sonnet, 1 lần/bài có cache).

**Tech Stack:** Python 3.11+, `anthropic` (Claude — Haiku cho classify, Sonnet cho synthesize), SQLite (stdlib), `unicodedata`/`re` (slug + heuristic). Không thêm dependency mới.

## Global Constraints

- Python **3.11+** (máy chạy 3.14.3). Chạy lệnh qua `.venv/Scripts/python` (Windows, Git Bash).
- **Local-first:** chỉ Anthropic (Claude) là dịch vụ trả phí.
- **Tiết kiệm token (bắt buộc):** ưu tiên Python. Classify: **heuristic Python trước**, chỉ gọi Claude (**Haiku**) khi heuristic không đủ chắc. Synthesize: gọi Claude (**Sonnet**) **1 lần/bài**, **cache theo `source_hash`** — không gọi lại nếu nguồn không đổi. Input gửi Claude phải cắt gọn; đặt `max_tokens` hợp lý.
- **Mock/inject Claude trong mọi unit test** — không gọi mạng. `classify_document` và `synthesize_lesson` nhận đối tượng Claude inject được.
- **KB tổ chức theo chương/bài/kỹ năng, KHÔNG theo ngày.** Cấu trúc thư mục: `kb/<mon>/lop<n>/<chuong-slug>/<bai-slug>/` chứa `lesson.md` + `meta.json`.
- `mon` chuẩn hóa thành slug: **`toan`** hoặc **`tieng-anh`**.
- Định danh code bằng tiếng Anh; chuỗi hiển thị/`lesson.md`/prompt bằng tiếng Việt.
- Trạng thái `documents.status`: `ingested` → `classified` (sau khi gán lesson) → `synthesized` (sau khi bài được tổng hợp).

## Bối cảnh code đã có (Phase 0 + 1A)

- `ai_tutor.config.Config`: có `kb_dir`, `data_dir`, `db_path`, `inbox_dir`, `processed_dir`, `failed_dir`. `load_config(root, env)`.
- `ai_tutor.db`: `connect(db_path)` (row_factory=Row, FK on), `init_db(conn)`. Bảng:
  - `documents(id, content_hash, source_path, file_type, status, extracted_text, lesson_id, created_at)`
  - `lessons(id, mon, lop, chuong, bai, dir_path, source_hash, created_at)` — `dir_path` UNIQUE
  - `skills(id, name UNIQUE)`, `lesson_skills(lesson_id, skill_id)`
- `ai_tutor.claude_client.ClaudeClient(client, *, cheap_model, smart_model)`; `.complete(system, user, *, smart=False, max_tokens=1024) -> str`; `.from_config(cfg)`. Thuộc tính nội bộ `_client`, `_cheap_model`, `_smart_model`.

## File Structure (Phase 1B)

```
src/ai_tutor/
  claude_client.py          # MODIFY: thêm complete_json() (structured output qua tool)
  classify/
    __init__.py             # tạo mới (rỗng)
    types.py                # Classification dataclass
    heuristics.py           # heuristic_classify() — pure Python
    classifier.py           # classify_document() — heuristic trước, Claude sau
  kb/
    __init__.py             # tạo mới (rỗng)
    paths.py                # slugify(), lesson_dir()
    store.py                # find_or_create_lesson(), assign_document_to_lesson()
    build.py                # build_kb() orchestrator + BuildReport
  synthesize/
    __init__.py             # tạo mới (rỗng)
    synthesizer.py          # compute_source_hash(), synthesize_lesson()
scripts/
  build_kb.py               # CLI: quét documents → KB
tests/
  test_claude_client.py     # MODIFY: thêm test complete_json
  classify/
    __init__.py
    test_heuristics.py
    test_classifier.py
  kb/
    __init__.py
    test_paths.py
    test_store.py
    test_build.py
  synthesize/
    __init__.py
    test_synthesizer.py
```

---

### Task 1: `ClaudeClient.complete_json` — structured output qua tool (cho Classify)

**Files:**
- Modify: `src/ai_tutor/claude_client.py`
- Test: `tests/test_claude_client.py`

**Interfaces:**
- Consumes: `ClaudeClient` hiện có.
- Produces: `complete_json(self, system: str, user: str, *, tool_name: str, tool_schema: dict, smart: bool = False, max_tokens: int = 512) -> dict` — gọi `messages.create` với `tools=[{name, description, input_schema}]` và `tool_choice={"type":"tool","name":tool_name}`, trả về `input` của block `type=="tool_use"` đầu tiên (dict), hoặc `{}` nếu không có.

- [ ] **Step 1: Viết test thất bại (fake client trả tool_use)**

Thêm vào cuối `tests/test_claude_client.py`:
```python
def test_complete_json_returns_tool_input_and_forces_tool():
    class FakeMsgs:
        def __init__(self): self.last = None
        def create(self, **kw):
            self.last = kw
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"lop": 3, "mon": "toan"})])
    class Fake:
        def __init__(self): self.messages = FakeMsgs()
    fake = Fake()
    client = ClaudeClient(fake)
    schema = {"type": "object", "properties": {"lop": {"type": "integer"}}}
    out = client.complete_json(system="s", user="u", tool_name="classify", tool_schema=schema)
    assert out == {"lop": 3, "mon": "toan"}
    assert fake.messages.last["tool_choice"] == {"type": "tool", "name": "classify"}
    assert fake.messages.last["tools"][0]["name"] == "classify"
    assert fake.messages.last["tools"][0]["input_schema"] == schema
    assert fake.messages.last["model"] == "claude-haiku-4-5-20251001"  # cheap by default
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/test_claude_client.py::test_complete_json_returns_tool_input_and_forces_tool -v`
Expected: FAIL (`AttributeError: ... has no attribute 'complete_json'`).

- [ ] **Step 3: Thêm method vào `src/ai_tutor/claude_client.py`**

Thêm vào trong class `ClaudeClient` (sau `complete`):
```python
    def complete_json(self, system: str, user: str, *, tool_name: str,
                      tool_schema: dict, smart: bool = False,
                      max_tokens: int = 512) -> dict:
        model = self._smart_model if smart else self._cheap_model
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[{"name": tool_name,
                    "description": "Trả kết quả theo schema.",
                    "input_schema": tool_schema}],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for b in resp.content:
            if getattr(b, "type", None) == "tool_use":
                return b.input
        return {}
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/test_claude_client.py -v`
Expected: PASS (gồm các test cũ + test mới).

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/claude_client.py tests/test_claude_client.py
git commit -m "feat(claude): complete_json — structured output qua tool (cho classify)"
```

---

### Task 2: `Classification` + heuristic phân loại (pure Python, không token)

**Files:**
- Create: `src/ai_tutor/classify/__init__.py` (rỗng), `src/ai_tutor/classify/types.py`, `src/ai_tutor/classify/heuristics.py`, `tests/classify/__init__.py` (rỗng), `tests/classify/test_heuristics.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Classification` với: `lop: int`, `mon: str` (`"toan"|"tieng-anh"`), `chuong: str | None`, `bai: str | None`, `ky_nang: tuple[str, ...]`, `source: str` (`"heuristic"|"claude"`).
  - `heuristic_classify(source_path: str, text: str) -> Classification | None` — trả `Classification(source="heuristic")` khi xác định được CẢ `lop` lẫn `mon`; ngược lại `None`. `chuong`/`bai` lấy được thì điền (dạng `"Chương N"`, `"Bài N"`, `"Unit N"`); `ky_nang` để trống `()`.

- [ ] **Step 1: Viết test thất bại**

`tests/classify/__init__.py`: (rỗng)

`tests/classify/test_heuristics.py`:
```python
from ai_tutor.classify.heuristics import heuristic_classify
from ai_tutor.classify.types import Classification


def test_detects_lop_mon_chuong_bai_from_path_and_text():
    c = heuristic_classify("inbox/_processed/toan-lop3.mp4",
                           "Chương 2 - Phép nhân. Bài 5: Bảng nhân 6.")
    assert isinstance(c, Classification)
    assert c.lop == 3 and c.mon == "toan"
    assert c.chuong == "Chương 2" and c.bai == "Bài 5"
    assert c.ky_nang == () and c.source == "heuristic"


def test_detects_english_unit():
    c = heuristic_classify("baitap.docx", "Tiếng Anh lớp 6 - Unit 3: Present Simple")
    assert c.lop == 6 and c.mon == "tieng-anh" and c.bai == "Unit 3"


def test_returns_none_when_uncertain():
    assert heuristic_classify("ghichu.txt", "hôm nay học bài mới") is None
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/classify/test_heuristics.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/classify/__init__.py`: (rỗng)

`src/ai_tutor/classify/types.py`:
```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    lop: int
    mon: str
    chuong: str | None
    bai: str | None
    ky_nang: tuple[str, ...]
    source: str
```

`src/ai_tutor/classify/heuristics.py`:
```python
from __future__ import annotations

import re
import unicodedata

from ai_tutor.classify.types import Classification


def _norm(s: str) -> str:
    """Bỏ dấu tiếng Việt + lowercase để dò từ khóa."""
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _detect_lop(n: str) -> int | None:
    m = re.search(r"lop\s*([36])", n)
    return int(m.group(1)) if m else None


def _detect_mon(n: str) -> str | None:
    if "tieng anh" in n or "english" in n or re.search(r"\bunit\b", n):
        return "tieng-anh"
    if "toan" in n or "math" in n:
        return "toan"
    return None


def _detect_chuong(n: str) -> str | None:
    m = re.search(r"chuong\s*(\d+)", n)
    return f"Chương {m.group(1)}" if m else None


def _detect_bai(n: str) -> str | None:
    m = re.search(r"\bbai\s*(\d+)", n)
    if m:
        return f"Bài {m.group(1)}"
    m = re.search(r"\bunit\s*(\d+)", n)
    if m:
        return f"Unit {m.group(1)}"
    return None


def heuristic_classify(source_path: str, text: str) -> Classification | None:
    n = _norm(f"{source_path} {text}")
    lop = _detect_lop(n)
    mon = _detect_mon(n)
    if lop is None or mon is None:
        return None
    return Classification(
        lop=lop, mon=mon,
        chuong=_detect_chuong(n), bai=_detect_bai(n),
        ky_nang=(), source="heuristic",
    )
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/classify/test_heuristics.py -v`
Expected: PASS cả 3 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/classify/__init__.py src/ai_tutor/classify/types.py src/ai_tutor/classify/heuristics.py tests/classify/__init__.py tests/classify/test_heuristics.py
git commit -m "feat(classify): Classification + heuristic phân loại (pure Python)"
```

---

### Task 3: `classify_document` — heuristic trước, Claude (Haiku) khi không chắc

**Files:**
- Create: `src/ai_tutor/classify/classifier.py`, `tests/classify/test_classifier.py`

**Interfaces:**
- Consumes: `heuristic_classify` (Task 2), `Classification` (Task 2), `ClaudeClient.complete_json` (Task 1).
- Produces: `classify_document(source_path: str, text: str, claude) -> Classification` — gọi `heuristic_classify`; nếu có kết quả → trả luôn (KHÔNG gọi Claude). Nếu `None` → gọi `claude.complete_json(...)` với `CLASSIFY_SCHEMA`, dựng `Classification(source="claude")` từ dict trả về (`lop` ép int; `mon` chuẩn hóa về `"toan"`/`"tieng-anh"`; `chuong`/`bai` = `None` nếu thiếu; `ky_nang` = tuple). Hằng `CLASSIFY_SCHEMA: dict` xuất khẩu.

- [ ] **Step 1: Viết test thất bại (fake claude đếm số lần gọi)**

`tests/classify/test_classifier.py`:
```python
from ai_tutor.classify.classifier import classify_document


class FakeClaude:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def complete_json(self, **kw):
        self.calls += 1
        return self.result


def test_uses_heuristic_without_calling_claude():
    claude = FakeClaude({"lop": 9, "mon": "toan"})  # sẽ không được dùng
    c = classify_document("toan-lop3.mp4", "Bài 5 bảng nhân 6", claude)
    assert c.lop == 3 and c.mon == "toan" and c.source == "heuristic"
    assert claude.calls == 0  # tiết kiệm token: không gọi Claude


def test_falls_back_to_claude_when_heuristic_uncertain():
    claude = FakeClaude({"lop": 6, "mon": "tieng-anh", "bai": "Unit 3",
                         "ky_nang": ["present-simple"]})
    c = classify_document("ghichu.txt", "nội dung mơ hồ", claude)
    assert claude.calls == 1
    assert c.lop == 6 and c.mon == "tieng-anh" and c.bai == "Unit 3"
    assert c.ky_nang == ("present-simple",) and c.source == "claude"
    assert c.chuong is None
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/classify/test_classifier.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/classify/classifier.py`:
```python
from __future__ import annotations

from ai_tutor.classify.heuristics import heuristic_classify
from ai_tutor.classify.types import Classification

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "lop": {"type": "integer", "description": "Lớp (3 hoặc 6)"},
        "mon": {"type": "string", "enum": ["toan", "tieng-anh"]},
        "chuong": {"type": "string"},
        "bai": {"type": "string"},
        "ky_nang": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["lop", "mon"],
}

_SYSTEM = (
    "Bạn phân loại tài liệu học tập của học sinh. Xác định lớp (3 hoặc 6), "
    "môn (toan hoặc tieng-anh), chương, bài và các kỹ năng chính. "
    "Chỉ trả qua công cụ theo schema."
)


def _norm_mon(value: str) -> str:
    v = (value or "").strip().lower()
    if v in ("toan", "toán", "math"):
        return "toan"
    return "tieng-anh"


def classify_document(source_path: str, text: str, claude) -> Classification:
    c = heuristic_classify(source_path, text)
    if c is not None:
        return c
    # Token-saving: chỉ tới đây khi heuristic không chắc. Cắt gọn input.
    snippet = text[:2000]
    data = claude.complete_json(
        system=_SYSTEM,
        user=f"Nguồn: {source_path}\n---\n{snippet}",
        tool_name="classify",
        tool_schema=CLASSIFY_SCHEMA,
    )
    return Classification(
        lop=int(data["lop"]),
        mon=_norm_mon(data["mon"]),
        chuong=data.get("chuong") or None,
        bai=data.get("bai") or None,
        ky_nang=tuple(data.get("ky_nang", [])),
        source="claude",
    )
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/classify/test_classifier.py -v`
Expected: PASS cả 2 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/classify/classifier.py tests/classify/test_classifier.py
git commit -m "feat(classify): classify_document — heuristic trước, Claude Haiku khi cần"
```

---

### Task 4: KB paths — slugify (bỏ dấu tiếng Việt) + lesson_dir

**Files:**
- Create: `src/ai_tutor/kb/__init__.py` (rỗng), `src/ai_tutor/kb/paths.py`, `tests/kb/__init__.py` (rỗng), `tests/kb/test_paths.py`

**Interfaces:**
- Consumes: `Classification` (Task 2).
- Produces:
  - `slugify(s: str) -> str` — bỏ dấu tiếng Việt (gồm `đ→d`), lowercase, ký tự không phải `[a-z0-9]` thành `-`, gộp `-` liên tiếp, cắt `-` đầu/cuối. Chuỗi rỗng/None-ish → `"khac"`.
  - `lesson_dir(kb_dir: Path, c: Classification) -> Path` — `kb_dir / c.mon / f"lop{c.lop}" / slugify(c.chuong or "khac") / slugify(c.bai or "khac")`.

- [ ] **Step 1: Viết test thất bại**

`tests/kb/__init__.py`: (rỗng)

`tests/kb/test_paths.py`:
```python
from pathlib import Path
from ai_tutor.kb.paths import slugify, lesson_dir
from ai_tutor.classify.types import Classification


def test_slugify_strips_vietnamese_accents():
    assert slugify("Chương 2 - Phép nhân") == "chuong-2-phep-nhan"
    assert slugify("Bài 5: Bảng nhân 6") == "bai-5-bang-nhan-6"
    assert slugify("đặt đúng") == "dat-dung"
    assert slugify("") == "khac"


def test_lesson_dir_layout():
    c = Classification(lop=3, mon="toan", chuong="Chương 2", bai="Bài 5",
                       ky_nang=(), source="heuristic")
    p = lesson_dir(Path("/kb"), c)
    assert p == Path("/kb/toan/lop3/chuong-2/bai-5")


def test_lesson_dir_none_chuong_bai_uses_khac():
    c = Classification(lop=6, mon="tieng-anh", chuong=None, bai=None,
                       ky_nang=(), source="claude")
    p = lesson_dir(Path("/kb"), c)
    assert p == Path("/kb/tieng-anh/lop6/khac/khac")
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/kb/test_paths.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/kb/__init__.py`: (rỗng)

`src/ai_tutor/kb/paths.py`:
```python
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from ai_tutor.classify.types import Classification


def slugify(s: str) -> str:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "khac"


def lesson_dir(kb_dir: Path, c: Classification) -> Path:
    return (kb_dir / c.mon / f"lop{c.lop}"
            / slugify(c.chuong or "khac") / slugify(c.bai or "khac"))
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/kb/test_paths.py -v`
Expected: PASS cả 3 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/kb/__init__.py src/ai_tutor/kb/paths.py tests/kb/__init__.py tests/kb/test_paths.py
git commit -m "feat(kb): slugify bỏ dấu tiếng Việt + lesson_dir"
```

---

### Task 5: KB store — find_or_create_lesson + gán document

**Files:**
- Create: `src/ai_tutor/kb/store.py`, `tests/kb/test_store.py`

**Interfaces:**
- Consumes: `Config`, `connect/init_db`, `Classification`, `lesson_dir` (Task 4).
- Produces:
  - `find_or_create_lesson(conn, cfg, c: Classification) -> int` — tính `dir_path = lesson_dir(cfg.kb_dir, c)`; nếu đã có hàng `lessons` cùng `dir_path` → trả `id`. Ngược lại: `mkdir(parents=True, exist_ok=True)`, INSERT `lessons(mon, lop, chuong, bai, dir_path)`, với mỗi kỹ năng trong `c.ky_nang` → `_find_or_create_skill` + INSERT `lesson_skills` (bỏ qua trùng), commit, trả `id`.
  - `assign_document_to_lesson(conn, doc_id: int, lesson_id: int) -> None` — `UPDATE documents SET lesson_id=?, status='classified' WHERE id=?`, commit.
  - `_find_or_create_skill(conn, name: str) -> int` (nội bộ, dùng được trong test).

- [ ] **Step 1: Viết test thất bại**

`tests/kb/test_store.py`:
```python
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.classify.types import Classification
from ai_tutor.kb.store import find_or_create_lesson, assign_document_to_lesson


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


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
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/kb/test_store.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/kb/store.py`:
```python
from __future__ import annotations

import sqlite3

from ai_tutor.classify.types import Classification
from ai_tutor.config import Config
from ai_tutor.kb.paths import lesson_dir


def _find_or_create_skill(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM skills WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO skills(name) VALUES(?)", (name,))
    return cur.lastrowid


def find_or_create_lesson(conn: sqlite3.Connection, cfg: Config,
                          c: Classification) -> int:
    dir_path = lesson_dir(cfg.kb_dir, c)
    key = str(dir_path)
    row = conn.execute("SELECT id FROM lessons WHERE dir_path=?", (key,)).fetchone()
    if row:
        return row["id"]
    dir_path.mkdir(parents=True, exist_ok=True)
    cur = conn.execute(
        "INSERT INTO lessons(mon, lop, chuong, bai, dir_path) VALUES (?,?,?,?,?)",
        (c.mon, c.lop, c.chuong, c.bai, key),
    )
    lesson_id = cur.lastrowid
    for skill in c.ky_nang:
        skill_id = _find_or_create_skill(conn, skill)
        conn.execute(
            "INSERT OR IGNORE INTO lesson_skills(lesson_id, skill_id) VALUES (?,?)",
            (lesson_id, skill_id),
        )
    conn.commit()
    return lesson_id


def assign_document_to_lesson(conn: sqlite3.Connection, doc_id: int,
                              lesson_id: int) -> None:
    conn.execute(
        "UPDATE documents SET lesson_id=?, status='classified' WHERE id=?",
        (lesson_id, doc_id),
    )
    conn.commit()
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/kb/test_store.py -v`
Expected: PASS cả 2 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/kb/store.py tests/kb/test_store.py
git commit -m "feat(kb): find_or_create_lesson + assign_document_to_lesson"
```

---

### Task 6: Synthesize — tổng hợp lesson.md 1 lần/bài, cache theo source_hash

**Files:**
- Create: `src/ai_tutor/synthesize/__init__.py` (rỗng), `src/ai_tutor/synthesize/synthesizer.py`, `tests/synthesize/__init__.py` (rỗng), `tests/synthesize/test_synthesizer.py`

**Interfaces:**
- Consumes: `Config`, `connect/init_db`, `ClaudeClient.complete` (smart), bảng `documents`/`lessons`.
- Produces:
  - `compute_source_hash(conn, lesson_id: int) -> str` — SHA-256 hex của danh sách `content_hash` (sắp xếp) của các `documents` thuộc `lesson_id`. Rỗng → hash của chuỗi rỗng.
  - `synthesize_lesson(conn, cfg, claude, lesson_id: int) -> Path | None` — tính `new_hash`; nếu `== lessons.source_hash` hiện tại → trả `None` (KHÔNG gọi Claude — cache). Ngược lại: gộp `extracted_text` của các document (cắt gọn), gọi `claude.complete(system=_SYSTEM, user=..., smart=True, max_tokens=1500)` để sinh `lesson.md`; ghi `lesson.md` + `meta.json` vào `lessons.dir_path`; cập nhật `lessons.source_hash=new_hash`; `UPDATE documents SET status='synthesized' WHERE lesson_id=?`; trả `Path(lesson.md)`.

- [ ] **Step 1: Viết test thất bại (fake claude đếm số lần gọi — kiểm tra cache)**

`tests/synthesize/__init__.py`: (rỗng)

`tests/synthesize/test_synthesizer.py`:
```python
from pathlib import Path
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.classify.types import Classification
from ai_tutor.kb.store import find_or_create_lesson, assign_document_to_lesson
from ai_tutor.synthesize.synthesizer import synthesize_lesson, compute_source_hash


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


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
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/synthesize/test_synthesizer.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/synthesize/__init__.py`: (rỗng)

`src/ai_tutor/synthesize/synthesizer.py`:
```python
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from ai_tutor.config import Config

_SYSTEM = (
    "Bạn là trợ giảng. Từ tài liệu của giáo viên dưới đây, hãy viết BẢN TỔNG HỢP "
    "kiến thức của bài bằng tiếng Việt, theo đúng cấu trúc markdown:\n"
    "# {Tên bài}\n## Tóm tắt lý thuyết\n## Công thức / Quy tắc chính\n"
    "## Ví dụ mẫu (kèm lời giải)\n## Lỗi thường gặp\n"
    "Chỉ dựa trên tài liệu được cung cấp, ngắn gọn, đúng trình độ học sinh."
)


def compute_source_hash(conn: sqlite3.Connection, lesson_id: int) -> str:
    rows = conn.execute(
        "SELECT content_hash FROM documents WHERE lesson_id=? ORDER BY content_hash",
        (lesson_id,),
    ).fetchall()
    joined = "\n".join(r["content_hash"] for r in rows)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def synthesize_lesson(conn: sqlite3.Connection, cfg: Config, claude,
                      lesson_id: int) -> Path | None:
    lesson = conn.execute(
        "SELECT mon, lop, chuong, bai, dir_path, source_hash FROM lessons WHERE id=?",
        (lesson_id,),
    ).fetchone()
    new_hash = compute_source_hash(conn, lesson_id)
    if lesson["source_hash"] == new_hash:
        return None  # cache: nguồn không đổi → không gọi Claude

    docs = conn.execute(
        "SELECT source_path, extracted_text FROM documents WHERE lesson_id=? ORDER BY id",
        (lesson_id,),
    ).fetchall()
    combined = "\n\n".join((d["extracted_text"] or "").strip() for d in docs)[:12000]
    header = f"{lesson['bai'] or 'Bài'} - {lesson['mon']} lớp {lesson['lop']}"
    md = claude.complete(
        system=_SYSTEM,
        user=f"Bài: {header}\n\n--- TÀI LIỆU ---\n{combined}",
        smart=True,
        max_tokens=1500,
    )

    dir_path = Path(lesson["dir_path"])
    dir_path.mkdir(parents=True, exist_ok=True)
    lesson_md = dir_path / "lesson.md"
    lesson_md.write_text(md, encoding="utf-8")

    skills = [r["name"] for r in conn.execute(
        "SELECT s.name FROM skills s JOIN lesson_skills ls ON ls.skill_id=s.id "
        "WHERE ls.lesson_id=?", (lesson_id,))]
    meta = {
        "mon": lesson["mon"], "lop": lesson["lop"],
        "chuong": lesson["chuong"], "bai": lesson["bai"],
        "ky_nang": skills,
        "nguon": [d["source_path"] for d in docs],
        "source_hash": new_hash,
    }
    (dir_path / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    conn.execute("UPDATE lessons SET source_hash=? WHERE id=?", (new_hash, lesson_id))
    conn.execute("UPDATE documents SET status='synthesized' WHERE lesson_id=?", (lesson_id,))
    conn.commit()
    return lesson_md
```

- [ ] **Step 4: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/synthesize/test_synthesizer.py -v`
Expected: PASS cả 2 test.

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/synthesize/__init__.py src/ai_tutor/synthesize/synthesizer.py tests/synthesize/__init__.py tests/synthesize/test_synthesizer.py
git commit -m "feat(synthesize): synthesize_lesson 1 lần/bài + cache source_hash"
```

---

### Task 7: `build_kb` orchestrator + CLI

**Files:**
- Create: `src/ai_tutor/kb/build.py`, `scripts/build_kb.py`, `tests/kb/test_build.py`

**Interfaces:**
- Consumes: `classify_document` (Task 3), `find_or_create_lesson`/`assign_document_to_lesson` (Task 5), `synthesize_lesson` (Task 6), `Config`, `ClaudeClient`.
- Produces:
  - `@dataclass BuildReport` với: `classified: int`, `lessons_touched: int`, `synthesized: int`.
  - `build_kb(cfg, conn, claude) -> BuildReport` — (1) với mỗi `documents` có `lesson_id IS NULL AND status='ingested' AND extracted_text IS NOT NULL`: `classify_document(source_path, extracted_text, claude)` → `find_or_create_lesson` → `assign_document_to_lesson` (đếm `classified`, gom tập `lesson_id` đụng tới). (2) với mỗi `lesson_id` trong tập đó: `synthesize_lesson(...)`; nếu trả Path (không phải None) → `synthesized += 1`. `lessons_touched = len(tập)`.

- [ ] **Step 1: Viết test thất bại (fake claude cho cả 2 method)**

`tests/kb/test_build.py`:
```python
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
    assert report2.synthesized == 0
```

- [ ] **Step 2: Chạy để xác nhận FAIL**

Run: `.venv/Scripts/python -m pytest tests/kb/test_build.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Viết code**

`src/ai_tutor/kb/build.py`:
```python
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
```

- [ ] **Step 4: Viết `scripts/build_kb.py`**

```python
from dotenv import load_dotenv
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.claude_client import ClaudeClient
from ai_tutor.kb.build import build_kb


def main() -> None:
    load_dotenv()
    cfg = load_config()
    conn = connect(cfg.db_path); init_db(conn)
    claude = ClaudeClient.from_config(cfg)
    report = build_kb(cfg, conn, claude)
    print(f"Phân loại: {report.classified} | Bài đụng tới: {report.lessons_touched} "
          f"| Tổng hợp mới: {report.synthesized}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Chạy test — PASS, rồi chạy toàn bộ suite**

Run: `.venv/Scripts/python -m pytest tests/kb/test_build.py -v`
Expected: PASS cả 2 test.
Run: `.venv/Scripts/python -m pytest -q`
Expected: toàn bộ PASS (Phase 0/1A + 1B).

- [ ] **Step 6: Commit**

```bash
git add src/ai_tutor/kb/build.py scripts/build_kb.py tests/kb/test_build.py
git commit -m "feat(kb): build_kb orchestrator (classify → lesson → synthesize) + CLI"
```

---

## Self-Review

**1. Spec coverage:**
- Classify heuristic-trước-Claude-sau, structured output, Haiku (spec §6, §1.1) → Task 1 (complete_json) + Task 2 (heuristic) + Task 3 (classifier). ✓
- KB theo chương/bài/kỹ năng, dir layout + meta.json (spec §4) → Task 4 (paths) + Task 5 (store) + Task 6 (meta.json). ✓
- Synthesize 1 lần/bài, template cố định, cache theo source_hash, amortize token (spec §6.5) → Task 6. ✓
- Tổng hợp theo CHỦ ĐỀ (xuyên bài) → spec để Phase 2, KHÔNG thuộc plan này. ✓ (đúng phạm vi)
- Tutor RAG (spec §7) → Phase 1C, không thuộc plan này. ✓

**2. Placeholder scan:** Không có "TBD/TODO"; mọi step code có code thật.

**3. Type consistency:** `Classification(lop, mon, chuong, bai, ky_nang, source)` đồng nhất Task 2→3→4→5. `complete_json(system, user, *, tool_name, tool_schema, smart, max_tokens)` (Task 1) khớp cách gọi ở Task 3. `find_or_create_lesson(conn, cfg, c) -> int` và `assign_document_to_lesson(conn, doc_id, lesson_id)` (Task 5) khớp cách dùng ở Task 7. `synthesize_lesson(conn, cfg, claude, lesson_id) -> Path | None` (Task 6) khớp Task 7. Trạng thái document `ingested→classified→synthesized` nhất quán giữa Task 5/6/7.

## Execution Handoff

Phase 1C (Tutor RAG — bot trả lời câu hỏi dựa trên `lesson.md`) sẽ là plan riêng sau khi plan này chạy xong.
