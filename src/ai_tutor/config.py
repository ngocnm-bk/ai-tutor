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
