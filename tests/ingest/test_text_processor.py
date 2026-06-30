from ai_tutor.ingest.processors.text_processor import extract_text


def test_extract_text_reads_and_strips(tmp_path):
    p = tmp_path / "n.txt"; p.write_text("  Bài 5: bảng nhân 6  \n", encoding="utf-8")
    assert extract_text(p) == "Bài 5: bảng nhân 6"
