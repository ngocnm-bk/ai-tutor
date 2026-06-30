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
