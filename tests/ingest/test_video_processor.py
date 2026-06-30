from ai_tutor.ingest.processors.video_processor import extract_text


def test_extract_text_uses_injected_transcriber(tmp_path):
    v = tmp_path / "lesson.mp4"; v.write_bytes(b"fakevideo")

    def transcribe(p): return "  Hôm nay cô dạy bảng nhân 6.  "

    assert extract_text(v, transcribe=transcribe) == "Hôm nay cô dạy bảng nhân 6."
