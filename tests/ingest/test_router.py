import pytest
from ai_tutor.ingest.router import detect_type


@pytest.mark.parametrize("name,expected", [
    ("a.txt", "text"), ("a.md", "text"), ("a.PDF", "pdf"),
    ("a.docx", "docx"), ("a.jpg", "image"), ("a.png", "image"),
    ("a.mp4", "video"), ("a.mp3", "video"), ("a.zip", "unknown"),
])
def test_detect_type(tmp_path, name, expected):
    p = tmp_path / name; p.write_bytes(b"x")
    assert detect_type(p) == expected
