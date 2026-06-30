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
