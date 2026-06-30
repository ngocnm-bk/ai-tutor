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
