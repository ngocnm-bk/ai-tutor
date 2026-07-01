# AI Tutor — LLM đa nhà cung cấp (OpenAI-compatible) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho phép chọn nhà cung cấp LLM (Gemini/OpenAI/Grok/Claude) qua `.env`, dùng một SDK `openai` với `base_url` khác nhau. Giữ nguyên interface `complete`/`complete_json`/thêm `vision` để phần còn lại của hệ thống gần như không đổi. Mặc định Gemini.

**Architecture:** `ClaudeClient` → `LLMClient` (file `llm.py`) bọc SDK `openai`; `from_config` tạo `OpenAI(api_key, base_url)`. Một registry provider ánh xạ provider → (base_url, key_env, model rẻ, model mạnh). `load_config` chọn provider từ `LLM_PROVIDER` (mặc định gemini), yêu cầu key tương ứng. `complete_json` chuyển sang JSON mode (portable giữa các nhà). Vision qua `image_url` base64.

**Tech Stack:** Python 3.11+, `openai` SDK (thay `anthropic`), SQLite. Không đổi logic nghiệp vụ.

## Global Constraints

- Python **3.11+** (máy chạy 3.14.3). Chạy qua `.venv/Scripts/python` (Windows, Git Bash).
- **Đa nhà cung cấp qua OpenAI-compatible endpoint**; đổi nhà = đổi `LLM_PROVIDER` trong `.env`. Mặc định **gemini**.
- **Giữ nguyên interface public** `LLMClient.complete(system, user, *, smart, max_tokens)` và `complete_json(system, user, *, tool_name, tool_schema, smart, max_tokens)` để `classifier.py`, `synthesizer.py`, `tutor_service.py` KHÔNG phải sửa. Thêm `vision(image_bytes, prompt, *, media_type, max_tokens, smart)`.
- **Tiết kiệm token / grounding / structured output cho classify: KHÔNG đổi** — chỉ đổi đường ống tới nhà cung cấp. `complete_json` vẫn ép JSON đúng schema (qua JSON mode).
- Model rẻ (classify) vs mạnh (dạy/tổng hợp) theo `smart` — giữ nguyên.
- **Mock/inject client trong mọi unit test** — không gọi mạng. Các fake LLM (`.complete`/`.complete_json`) inject vào hàm nghiệp vụ KHÔNG đổi (interface public giữ nguyên); chỉ test client (`llm`) và config đổi theo.
- Registry model mặc định (đều override được qua `LLM_CHEAP_MODEL`/`LLM_SMART_MODEL`):
  - gemini: `gemini-2.5-flash` / `gemini-2.5-pro`
  - openai: `gpt-4o-mini` / `gpt-4o`
  - grok: `grok-3-mini` / `grok-3`
  - claude: `claude-haiku-4-5-20251001` / `claude-sonnet-4-6`
- base_url: gemini `https://generativelanguage.googleapis.com/v1beta/openai/` · openai mặc định (None) · grok `https://api.x.ai/v1` · claude `https://api.anthropic.com/v1/`.

## File Structure

```
src/ai_tutor/
  providers.py         # tạo mới: ProviderSpec + PROVIDERS registry
  config.py            # MODIFY: chọn provider, bỏ ràng buộc cứng ANTHROPIC_API_KEY, thêm llm_* fields
  llm.py               # tạo mới (thay claude_client.py): LLMClient (complete/complete_json/vision/from_config)
  claude_client.py     # XÓA
  ingest/pipeline.py   # MODIFY: vision dùng llm.vision (bỏ gọi kiểu Anthropic)
scripts/
  ingest_once.py, run_bot.py, build_kb.py   # MODIFY: ClaudeClient → LLMClient
tests/
  test_config.py       # MODIFY: provider gemini mặc định + override + thiếu key
  test_llm.py          # tạo mới (thay test_claude_client.py): fake OpenAI client
  test_claude_client.py# XÓA
  <các test dùng env ANTHROPIC_API_KEY>  # MODIFY: đổi sang GEMINI_API_KEY
pyproject.toml         # MODIFY: bỏ anthropic, thêm openai
.env.example           # MODIFY: LLM_PROVIDER + các key
```

---

### Task 1: providers registry + config.py + .env.example

**Files:**
- Create: `src/ai_tutor/providers.py`
- Modify: `src/ai_tutor/config.py`, `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) ProviderSpec(base_url: str | None, key_env: str, cheap_model: str, smart_model: str)`; `PROVIDERS: dict[str, ProviderSpec]` với keys `gemini/openai/grok/claude`.
  - `Config` (bỏ field `anthropic_api_key`; THÊM `llm_provider: str`, `llm_api_key: str`, `llm_base_url: str | None`, `llm_cheap_model: str`, `llm_smart_model: str`; giữ `telegram_bot_token`, các path).
  - `load_config(root, env)` — `provider = (env.get("LLM_PROVIDER") or "gemini").lower()`; lỗi `ValueError` nếu provider lạ; bắt buộc `TELEGRAM_BOT_TOKEN` và key `PROVIDERS[provider].key_env`; model = `env.get("LLM_CHEAP_MODEL") or spec.cheap_model` (tương tự smart); `base_url = env.get("LLM_BASE_URL") or spec.base_url`.

- [ ] **Step 1: Viết test thất bại**

Thay nội dung `tests/test_config.py`:
```python
from pathlib import Path
import pytest
from ai_tutor.config import load_config


def test_default_provider_is_gemini(tmp_path: Path):
    cfg = load_config(root=tmp_path, env={"GEMINI_API_KEY": "g", "TELEGRAM_BOT_TOKEN": "t"})
    assert cfg.llm_provider == "gemini"
    assert cfg.llm_api_key == "g"
    assert cfg.llm_base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert cfg.llm_cheap_model == "gemini-2.5-flash"
    assert cfg.llm_smart_model == "gemini-2.5-pro"
    assert cfg.inbox_dir.is_dir() and cfg.db_path == tmp_path / "data" / "ai_tutor.db"


def test_select_openai_and_override_models(tmp_path: Path):
    cfg = load_config(root=tmp_path, env={
        "LLM_PROVIDER": "openai", "OPENAI_API_KEY": "o", "TELEGRAM_BOT_TOKEN": "t",
        "LLM_SMART_MODEL": "gpt-5",
    })
    assert cfg.llm_provider == "openai" and cfg.llm_base_url is None
    assert cfg.llm_cheap_model == "gpt-4o-mini"
    assert cfg.llm_smart_model == "gpt-5"  # override thắng


def test_missing_provider_key_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        load_config(root=tmp_path, env={"LLM_PROVIDER": "grok", "TELEGRAM_BOT_TOKEN": "t"})


def test_missing_telegram_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        load_config(root=tmp_path, env={"GEMINI_API_KEY": "g"})


def test_unknown_provider_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        load_config(root=tmp_path, env={"LLM_PROVIDER": "llama", "TELEGRAM_BOT_TOKEN": "t"})
```

- [ ] **Step 2: Chạy FAIL**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL (Config chưa có `llm_provider`, load_config chưa hỗ trợ).

- [ ] **Step 3: Viết `src/ai_tutor/providers.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    base_url: str | None
    key_env: str
    cheap_model: str
    smart_model: str


PROVIDERS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "GEMINI_API_KEY", "gemini-2.5-flash", "gemini-2.5-pro"),
    "openai": ProviderSpec(
        None, "OPENAI_API_KEY", "gpt-4o-mini", "gpt-4o"),
    "grok": ProviderSpec(
        "https://api.x.ai/v1", "XAI_API_KEY", "grok-3-mini", "grok-3"),
    "claude": ProviderSpec(
        "https://api.anthropic.com/v1/", "ANTHROPIC_API_KEY",
        "claude-haiku-4-5-20251001", "claude-sonnet-4-6"),
}
```

- [ ] **Step 4: Sửa `src/ai_tutor/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ai_tutor.providers import PROVIDERS


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    llm_provider: str
    llm_api_key: str
    llm_base_url: str | None
    llm_cheap_model: str
    llm_smart_model: str
    root: Path
    inbox_dir: Path
    failed_dir: Path
    processed_dir: Path
    kb_dir: Path
    data_dir: Path
    db_path: Path


def load_config(root: Path | None = None, env: Mapping[str, str] | None = None) -> Config:
    env = env if env is not None else os.environ
    root = (root or Path.cwd()).resolve()

    provider = (env.get("LLM_PROVIDER") or "gemini").lower()
    if provider not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER không hợp lệ: {provider} "
                         f"(chọn: {', '.join(PROVIDERS)})")
    spec = PROVIDERS[provider]

    try:
        telegram = env["TELEGRAM_BOT_TOKEN"]
    except KeyError as missing:
        raise ValueError(f"Thiếu biến môi trường bắt buộc: {missing}") from missing

    api_key = env.get(spec.key_env)
    if not api_key:
        raise ValueError(f"Thiếu {spec.key_env} cho LLM_PROVIDER={provider}")

    cheap = env.get("LLM_CHEAP_MODEL") or spec.cheap_model
    smart = env.get("LLM_SMART_MODEL") or spec.smart_model
    base_url = env.get("LLM_BASE_URL") or spec.base_url

    inbox_dir = root / "inbox"
    failed_dir = inbox_dir / "_failed"
    processed_dir = inbox_dir / "_processed"
    kb_dir = root / "kb"
    data_dir = root / "data"
    for d in (inbox_dir, failed_dir, processed_dir, kb_dir, data_dir):
        d.mkdir(parents=True, exist_ok=True)

    return Config(
        telegram_bot_token=telegram,
        llm_provider=provider,
        llm_api_key=api_key,
        llm_base_url=base_url,
        llm_cheap_model=cheap,
        llm_smart_model=smart,
        root=root,
        inbox_dir=inbox_dir,
        failed_dir=failed_dir,
        processed_dir=processed_dir,
        kb_dir=kb_dir,
        data_dir=data_dir,
        db_path=data_dir / "ai_tutor.db",
    )
```

- [ ] **Step 5: Sửa `.env.example`**

```dotenv
# Nhà cung cấp LLM: gemini | openai | grok | claude (mặc định gemini)
LLM_PROVIDER=gemini
# Điền key của (các) nhà bạn dùng:
GEMINI_API_KEY=
OPENAI_API_KEY=
XAI_API_KEY=
ANTHROPIC_API_KEY=
# (tùy chọn) ép model / endpoint, bỏ trống thì dùng mặc định theo provider:
LLM_CHEAP_MODEL=
LLM_SMART_MODEL=
LLM_BASE_URL=
# Telegram bot (từ @BotFather):
TELEGRAM_BOT_TOKEN=
```

- [ ] **Step 6: Chạy test — PASS**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: PASS cả 5 test.

- [ ] **Step 7: Commit**

```bash
git add src/ai_tutor/providers.py src/ai_tutor/config.py .env.example tests/test_config.py
git commit -m "feat(config): chọn LLM provider qua .env (registry + gemini mặc định)"
```

---

### Task 2: LLMClient (llm.py) thay claude_client.py + đổi deps

**Files:**
- Create: `src/ai_tutor/llm.py`, `tests/test_llm.py`
- Delete: `src/ai_tutor/claude_client.py`, `tests/test_claude_client.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `Config` (llm_* fields), SDK `openai`.
- Produces `class LLMClient`:
  - `__init__(client, *, cheap_model, smart_model)`.
  - `from_config(cfg) -> LLMClient` — `OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_base_url)`.
  - `complete(system, user, *, smart=False, max_tokens=1024) -> str` — `chat.completions.create(model, max_tokens, messages=[system,user])` → `choices[0].message.content or ""`.
  - `complete_json(system, user, *, tool_name, tool_schema, smart=False, max_tokens=512) -> dict` — nhét schema vào system, `response_format={"type":"json_object"}`, parse JSON có fallback. (`tool_name` giữ để tương thích chữ ký, không dùng.)
  - `vision(image_bytes, prompt, *, media_type="image/png", max_tokens=1024, smart=False) -> str` — messages có `image_url` data-URI base64.

- [ ] **Step 1: Viết test thất bại (fake OpenAI-style client)**

`tests/test_llm.py`:
```python
import json
from types import SimpleNamespace
from unittest.mock import patch
from ai_tutor.llm import LLMClient


def _resp(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeCompletions:
    def __init__(self, content): self.content = content; self.last = None
    def create(self, **kw): self.last = kw; return _resp(self.content)


class FakeClient:
    def __init__(self, content="xin chào"):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def test_complete_uses_cheap_model_and_returns_text():
    fake = FakeClient("xin chào")
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    out = c.complete("s", "u")
    assert out == "xin chào"
    kw = fake.chat.completions.last
    assert kw["model"] == "cheap"
    assert kw["messages"][0]["role"] == "system" and kw["messages"][1]["role"] == "user"


def test_complete_smart_uses_smart_model():
    fake = FakeClient()
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    c.complete("s", "u", smart=True, max_tokens=200)
    assert fake.chat.completions.last["model"] == "smart"
    assert fake.chat.completions.last["max_tokens"] == 200


def test_complete_json_parses_json_mode():
    fake = FakeClient(json.dumps({"lop": 3, "mon": "toan"}))
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    out = c.complete_json("s", "u", tool_name="classify", tool_schema={"type": "object"})
    assert out == {"lop": 3, "mon": "toan"}
    assert fake.chat.completions.last["response_format"] == {"type": "json_object"}


def test_complete_json_lenient_on_extra_text():
    fake = FakeClient('Đây là kết quả: {"lop": 6, "mon": "tieng-anh"} .')
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    assert c.complete_json("s", "u", tool_name="x", tool_schema={})["lop"] == 6


def test_vision_sends_image_url():
    fake = FakeClient("6 x 7 = ?")
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    out = c.vision(b"IMG", "trích text", media_type="image/png")
    assert out == "6 x 7 = ?"
    content = fake.chat.completions.last["messages"][0]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_from_config_builds_openai_client():
    cfg = SimpleNamespace(llm_api_key="k", llm_base_url="http://x",
                          llm_cheap_model="c", llm_smart_model="s")
    with patch("openai.OpenAI") as MockOpenAI:
        MockOpenAI.return_value = SimpleNamespace(chat=None)
        c = LLMClient.from_config(cfg)
    MockOpenAI.assert_called_once_with(api_key="k", base_url="http://x")
    assert isinstance(c, LLMClient)
```

- [ ] **Step 2: Chạy FAIL**

Run: `.venv/Scripts/python -m pytest tests/test_llm.py -v`
Expected: FAIL (`ModuleNotFoundError: ai_tutor.llm`).

- [ ] **Step 3: Xóa file cũ + viết `src/ai_tutor/llm.py`**

```bash
git rm src/ai_tutor/claude_client.py tests/test_claude_client.py
```

`src/ai_tutor/llm.py`:
```python
from __future__ import annotations

import base64
import json
import re


class LLMClient:
    def __init__(self, client, *, cheap_model: str, smart_model: str):
        self._client = client
        self._cheap_model = cheap_model
        self._smart_model = smart_model

    @classmethod
    def from_config(cls, cfg) -> "LLMClient":
        from openai import OpenAI
        client = OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_base_url)
        return cls(client, cheap_model=cfg.llm_cheap_model,
                   smart_model=cfg.llm_smart_model)

    def _model(self, smart: bool) -> str:
        return self._smart_model if smart else self._cheap_model

    def complete(self, system: str, user: str, *, smart: bool = False,
                 max_tokens: int = 1024) -> str:
        resp = self._client.chat.completions.create(
            model=self._model(smart),
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""

    def complete_json(self, system: str, user: str, *, tool_name: str,
                      tool_schema: dict, smart: bool = False,
                      max_tokens: int = 512) -> dict:
        system2 = (system + "\n\nCHỈ trả về DUY NHẤT một JSON hợp lệ đúng schema "
                   "sau, không kèm giải thích:\n"
                   + json.dumps(tool_schema, ensure_ascii=False))
        resp = self._client.chat.completions.create(
            model=self._model(smart),
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system2},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
        )
        return _loads_lenient(resp.choices[0].message.content or "{}")

    def vision(self, image_bytes: bytes, prompt: str, *,
               media_type: str = "image/png", max_tokens: int = 1024,
               smart: bool = False) -> str:
        data = base64.standard_b64encode(image_bytes).decode()
        resp = self._client.chat.completions.create(
            model=self._model(smart),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{media_type};base64,{data}"}},
            ]}],
        )
        return resp.choices[0].message.content or ""


def _loads_lenient(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {}
```

- [ ] **Step 4: Sửa `pyproject.toml` (bỏ anthropic, thêm openai)**

Trong `[project] dependencies`: thay dòng `"anthropic>=0.40",` bằng `"openai>=1.40",`.

- [ ] **Step 5: Cài openai + chạy test — PASS**

Run: `.venv/Scripts/python -m pip install "openai>=1.40" && .venv/Scripts/python -m pytest tests/test_llm.py -v`
Expected: PASS cả 6 test.

- [ ] **Step 6: Commit**

```bash
git add src/ai_tutor/llm.py tests/test_llm.py pyproject.toml
git commit -m "feat(llm): LLMClient qua openai SDK (complete/complete_json JSON-mode/vision)"
```

---

### Task 3: Wiring — pipeline vision + scripts + sweep test env

**Files:**
- Modify: `src/ai_tutor/ingest/pipeline.py`, `scripts/ingest_once.py`, `scripts/run_bot.py`, `scripts/build_kb.py`
- Modify (sweep env): `tests/ingest/test_pipeline.py`, `tests/kb/test_build.py`, `tests/kb/test_retrieval.py`, `tests/kb/test_store.py`, `tests/synthesize/test_synthesizer.py`, `tests/tutor/test_tutor_service.py`, `tests/tutor/test_bot_handlers.py`

**Interfaces:**
- Consumes: `LLMClient` (Task 2), `Config` (Task 1).
- Produces: `build_default_extractors(llm)` (đổi tên tham số `claude`→`llm`) dùng `llm.vision(...)`; các script dùng `LLMClient.from_config`.

- [ ] **Step 1: Sửa `ingest/pipeline.py` — hàm vision dùng `llm.vision`**

Đổi `build_default_extractors(claude)` thành:
```python
def build_default_extractors(llm) -> dict[str, Extractor]:
    from ai_tutor.ingest.processors import (
        text_processor, pdf_processor, docx_processor,
        image_processor, video_processor,
    )

    def vision(p: Path) -> str:
        # Token-saving: chỉ chạy khi OCR cục bộ kém (image_processor quyết định).
        media = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return llm.vision(p.read_bytes(),
                          "Trích toàn bộ chữ/đề bài trong ảnh. Chỉ trả text.",
                          media_type=media)

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

- [ ] **Step 2: Sửa 3 script — `ClaudeClient` → `LLMClient`**

Trong `scripts/ingest_once.py`, `scripts/run_bot.py`, `scripts/build_kb.py`:
- đổi `from ai_tutor.claude_client import ClaudeClient` → `from ai_tutor.llm import LLMClient`
- đổi `ClaudeClient.from_config(cfg)` → `LLMClient.from_config(cfg)`
- (giữ tên biến `claude` hay đổi `llm` đều được; nếu `ingest_once.py` gọi `build_default_extractors(claude)` thì truyền đúng biến đó.)

- [ ] **Step 3: Sweep env trong test — `ANTHROPIC_API_KEY` → `GEMINI_API_KEY`**

Trong các file test liệt kê ở trên, đổi mọi `env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"}` (và biến thể) thành `env={"GEMINI_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"}`. (Các fake LLM inject `.complete`/`.complete_json` GIỮ NGUYÊN — interface public không đổi.)

Lệnh gợi ý để tìm chỗ còn sót:
```bash
grep -rn "ANTHROPIC_API_KEY" tests/
```

- [ ] **Step 4: Chạy TOÀN BỘ suite — PASS**

Run: `.venv/Scripts/python -m pytest -q`
Expected: toàn bộ PASS (số lượng như trước khi refactor). Không còn tham chiếu `ClaudeClient`/`ANTHROPIC_API_KEY` trong `src`/`scripts`/`tests` (trừ `providers.py` map claude→`ANTHROPIC_API_KEY`, đó là đúng).

- [ ] **Step 5: Commit**

```bash
git add src/ai_tutor/ingest/pipeline.py scripts/ tests/
git commit -m "refactor: dùng LLMClient toàn hệ thống (vision + scripts + test env gemini)"
```

---

### Task 4: Docs — CLAUDE.md + spec + README lệnh

**Files:**
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-06-30-ai-tutor-design.md`

**Interfaces:** không có code; chỉ cập nhật tài liệu cho khớp thực tế đa nhà cung cấp.

- [ ] **Step 1: Cập nhật `CLAUDE.md`**

- Mục "Cấu hình & bí mật": thay `ANTHROPIC_API_KEY` bằng mô tả `LLM_PROVIDER` + các key nhà cung cấp (gemini/openai/grok/claude), model override.
- Mục "Mô hình Claude" → đổi tiêu đề thành "Mô hình LLM (đa nhà cung cấp)": nêu chọn provider qua `.env`, mặc định Gemini, dùng SDK `openai` OpenAI-compatible, `LLMClient` interface `complete`/`complete_json`/`vision`, model rẻ (classify) vs mạnh (dạy/tổng hợp).
- Thư viện chính: thay `anthropic` bằng `openai`.
- Nguyên tắc tiết kiệm token: giữ nguyên nội dung, chỉ đổi từ "Claude" → "LLM/model" nơi phù hợp (vẫn nói rõ chỉ LLM tốn phí).

- [ ] **Step 2: Cập nhật spec `docs/superpowers/specs/2026-06-30-ai-tutor-design.md`**

- Thêm một đoạn ở mục Công nghệ (mục 12): hệ thống hỗ trợ **đa nhà cung cấp LLM** (Gemini mặc định, hoặc OpenAI/Grok/Claude) qua endpoint OpenAI-compatible; đổi nhà = đổi `LLM_PROVIDER`. Bảng registry model/base_url.
- Sửa các câu "chỉ Claude tốn phí" → "chỉ LLM (nhà cung cấp đã chọn) tốn phí".

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-06-30-ai-tutor-design.md
git commit -m "docs: cập nhật tài liệu cho LLM đa nhà cung cấp"
```

---

## Self-Review

**1. Spec coverage:** đổi nhà cung cấp qua `.env` (Task 1), một SDK openai với base_url (Task 2), giữ interface + JSON mode cho classify + vision (Task 2), wiring toàn hệ thống + test (Task 3), docs (Task 4). ✓
**2. Placeholder scan:** không có "TBD/TODO"; mọi step code có code thật hoặc chỉ dẫn sửa cụ thể (Task 3/4 là chỉnh sửa cơ học có nêu rõ from→to).
**3. Type consistency:** `LLMClient` interface `complete(system,user,*,smart,max_tokens)` + `complete_json(system,user,*,tool_name,tool_schema,smart,max_tokens)` GIỮ NGUYÊN chữ ký so với `ClaudeClient` cũ → `classifier.py`/`synthesizer.py`/`tutor_service.py` không đổi. `Config.llm_*` (Task 1) khớp `LLMClient.from_config` (Task 2). `build_default_extractors(llm)` (Task 3) khớp cách gọi trong `scripts/ingest_once.py`.

## Execution Handoff

Sau refactor này, mọi phase sau (2/3) chạy trên nhà cung cấp đã chọn; muốn đổi nhà chỉ cần sửa `.env` (`LLM_PROVIDER` + key).
