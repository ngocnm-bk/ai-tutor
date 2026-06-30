from __future__ import annotations

from pathlib import Path

import docx


def extract_text(path: Path) -> str:
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs).strip()
