from pathlib import Path
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.ingest.pipeline import ingest_once


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"GEMINI_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


def _extractors():
    return {
        "text": lambda p: f"TEXT:{p.read_text(encoding='utf-8')}",
        "pdf": lambda p: "PDF",
        "image": lambda p: (_ for _ in ()).throw(RuntimeError("ocr boom")),
    }


def test_ingest_stores_documents_and_isolates_errors(tmp_path):
    cfg = _cfg(tmp_path)
    (cfg.inbox_dir / "a.txt").write_text("bài 5", encoding="utf-8")
    (cfg.inbox_dir / "b.png").write_bytes(b"img")     # extractor sẽ ném lỗi
    conn = connect(cfg.db_path); init_db(conn)

    report = ingest_once(cfg, conn, extractors=_extractors())

    assert report.ingested == 1
    assert report.failed == 1
    assert report.failed_files == ["b.png"]
    rows = conn.execute("SELECT file_type, extracted_text, source_path FROM documents").fetchall()
    # source_path trỏ vào _processed (vị trí thật sau move), không phải inbox gốc
    assert rows[0]["source_path"] == str(cfg.processed_dir / "a.txt")
    assert rows[0]["file_type"] == "text"
    assert "bài 5" in rows[0]["extracted_text"]
    assert not (cfg.inbox_dir / "b.png").exists()           # đã move
    assert (cfg.failed_dir / "b.png").exists()
    # File đã nạp được GIỮ LẠI (chuyển sang _processed), không bị xóa
    assert not (cfg.inbox_dir / "a.txt").exists()
    assert (cfg.processed_dir / "a.txt").exists()


def test_ingest_skips_duplicate_hash(tmp_path):
    cfg = _cfg(tmp_path)
    (cfg.inbox_dir / "a.txt").write_text("same", encoding="utf-8")
    conn = connect(cfg.db_path); init_db(conn)
    ingest_once(cfg, conn, extractors=_extractors())

    (cfg.inbox_dir / "copy.txt").write_text("same", encoding="utf-8")  # cùng nội dung
    report = ingest_once(cfg, conn, extractors=_extractors())
    assert report.skipped == 1
    assert report.ingested == 0


def test_success_collision_two_runs_both_preserved(tmp_path):
    """Two different files sharing the same name across two runs both succeed.

    _processed must end with 2 files, and every documents.source_path must
    point to an existing file (no phantom rows, no crash on Windows).
    """
    cfg = _cfg(tmp_path)
    conn = connect(cfg.db_path)
    init_db(conn)

    # Run 1: a.txt with content "run1"
    (cfg.inbox_dir / "a.txt").write_text("run1", encoding="utf-8")
    report1 = ingest_once(cfg, conn, extractors=_extractors())
    assert report1.ingested == 1
    assert report1.failed == 0

    # Run 2: different content (different hash → not deduped), same filename
    (cfg.inbox_dir / "a.txt").write_text("run2", encoding="utf-8")
    report2 = ingest_once(cfg, conn, extractors=_extractors())
    assert report2.ingested == 1
    assert report2.failed == 0

    # Both files must be present in _processed (collision-safe rename)
    processed_files = list(cfg.processed_dir.iterdir())
    assert len(processed_files) == 2, (
        f"Expected 2 files in _processed, got {[f.name for f in processed_files]}"
    )

    # Every source_path in the DB must point to an existing file (no phantom rows)
    rows = conn.execute("SELECT source_path FROM documents").fetchall()
    assert len(rows) == 2
    for row in rows:
        assert Path(row["source_path"]).exists(), (
            f"Phantom row: {row['source_path']} does not exist"
        )


def test_failure_collision_two_runs_no_crash(tmp_path):
    """Two different same-named files that both FAIL across two runs.

    The second run must not crash, report.failed == 1 each run, and _failed
    must end with 2 files (both preserved, collision-safe rename).
    """
    cfg = _cfg(tmp_path)
    conn = connect(cfg.db_path)
    init_db(conn)

    # Run 1: b.png fails (image extractor raises)
    (cfg.inbox_dir / "b.png").write_bytes(b"img1")
    report1 = ingest_once(cfg, conn, extractors=_extractors())
    assert report1.failed == 1
    assert report1.failed_files == ["b.png"]

    # Run 2: different content (different hash), same filename — must not crash
    (cfg.inbox_dir / "b.png").write_bytes(b"img2")
    report2 = ingest_once(cfg, conn, extractors=_extractors())
    assert report2.failed == 1
    assert report2.failed_files == ["b.png"]

    # Both files must be present in _failed (collision-safe rename)
    failed_files = list(cfg.failed_dir.iterdir())
    assert len(failed_files) == 2, (
        f"Expected 2 files in _failed, got {[f.name for f in failed_files]}"
    )
