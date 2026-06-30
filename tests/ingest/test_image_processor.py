from pathlib import Path
from ai_tutor.ingest.processors.image_processor import extract_text


def test_uses_local_ocr_when_enough_text(tmp_path):
    img = tmp_path / "a.png"; img.write_bytes(b"x")
    calls = {"vision": 0}

    def ocr(p): return "Bài 5: bảng nhân 6 — đủ dài để dùng được"

    def vision(p):
        calls["vision"] += 1
        return "VISION"

    out = extract_text(img, ocr=ocr, vision=vision)
    assert "bảng nhân 6" in out
    assert calls["vision"] == 0  # KHÔNG gọi Claude


def test_falls_back_to_vision_when_ocr_poor(tmp_path):
    img = tmp_path / "a.png"; img.write_bytes(b"x")

    def ocr(p): return "  ?? "  # quá ít ký tự

    def vision(p): return "Đề bài: 6 x 7 = ?"

    out = extract_text(img, ocr=ocr, vision=vision)
    assert out == "Đề bài: 6 x 7 = ?"
