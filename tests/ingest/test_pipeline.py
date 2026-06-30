from pathlib import Path
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.ingest.pipeline import ingest_once


def _cfg(tmp_path):
    return load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"})


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
    rows = conn.execute("SELECT file_type, extracted_text FROM documents").fetchall()
    assert rows[0]["file_type"] == "text"
    assert "bài 5" in rows[0]["extracted_text"]
    assert not (cfg.inbox_dir / "b.png").exists()           # đã move
    assert (cfg.failed_dir / "b.png").exists()


def test_ingest_skips_duplicate_hash(tmp_path):
    cfg = _cfg(tmp_path)
    (cfg.inbox_dir / "a.txt").write_text("same", encoding="utf-8")
    conn = connect(cfg.db_path); init_db(conn)
    ingest_once(cfg, conn, extractors=_extractors())

    (cfg.inbox_dir / "copy.txt").write_text("same", encoding="utf-8")  # cùng nội dung
    report = ingest_once(cfg, conn, extractors=_extractors())
    assert report.skipped == 1
    assert report.ingested == 0
