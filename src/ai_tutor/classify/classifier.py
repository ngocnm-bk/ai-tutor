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
