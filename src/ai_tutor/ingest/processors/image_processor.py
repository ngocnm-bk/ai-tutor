from __future__ import annotations

from pathlib import Path
from typing import Callable


def extract_text(path: Path, *, ocr: Callable[[Path], str],
                 vision: Callable[[Path], str], min_chars: int = 20) -> str:
    local = (ocr(path) or "").strip()
    if len(local) >= min_chars:
        return local
    return (vision(path) or "").strip()


def default_ocr(path: Path) -> str:
    import pytesseract
    from PIL import Image
    img = Image.open(path)
    try:
        return pytesseract.image_to_string(img, lang="vie+eng")
    except pytesseract.TesseractError:
        return pytesseract.image_to_string(img)
