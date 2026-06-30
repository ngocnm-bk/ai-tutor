from ai_tutor.ingest.hashing import file_content_hash


def test_hash_is_stable_and_content_based(tmp_path):
    a = tmp_path / "a.txt"; a.write_text("hello", encoding="utf-8")
    b = tmp_path / "b.txt"; b.write_text("hello", encoding="utf-8")
    c = tmp_path / "c.txt"; c.write_text("world", encoding="utf-8")
    assert file_content_hash(a) == file_content_hash(b)
    assert file_content_hash(a) != file_content_hash(c)
    assert len(file_content_hash(a)) == 64
