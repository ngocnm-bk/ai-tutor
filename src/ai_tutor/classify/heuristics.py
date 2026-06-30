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
    # Cố ý chỉ nhận lớp 3 và 6 (phạm vi dự án: 2 con lớp 3 & 6). Giới hạn [36]
    # còn an toàn hơn \d+ vì tránh khớp nhầm số lớp khác xuất hiện trong câu.
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
