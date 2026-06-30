import pytest
from ai_tutor.ingest.processors.pdf_processor import extract_text


def _make_pdf_with_text(path, text):
    # pypdf không tạo text trang; dùng reportlab nếu có, ngược lại skip.
    rl = pytest.importorskip("reportlab.pdfgen.canvas")
    c = rl.Canvas(str(path))
    c.drawString(72, 720, text)
    c.save()


def test_extract_text_from_pdf(tmp_path):
    p = tmp_path / "d.pdf"
    _make_pdf_with_text(p, "Chuong 2 phep nhan")
    assert "phep nhan" in extract_text(p).lower()
