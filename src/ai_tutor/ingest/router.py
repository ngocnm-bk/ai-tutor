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
