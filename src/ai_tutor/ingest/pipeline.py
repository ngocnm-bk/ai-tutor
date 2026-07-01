from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ai_tutor.config import Config
from ai_tutor.ingest.hashing import file_content_hash
from ai_tutor.ingest.router import detect_type

Extractor = Callable[[Path], str]


@dataclass
class IngestReport:
    ingested: int = 0
    skipped: int = 0
    failed: int = 0
    failed_files: list[str] = field(default_factory=list)


def _iter_inbox(cfg: Config):
    for p in sorted(cfg.inbox_dir.iterdir()):
        if p.is_dir() or p.name.startswith(".") or p.name in ("_failed", "_processed"):
            continue
        yield p


def _move_no_clobber(src: Path, dest_dir: Path) -> Path:
    """Move src into dest_dir, choosing a non-existing filename to avoid collisions."""
    dest = dest_dir / src.name
    i = 1
    while dest.exists():
        dest = dest_dir / f"{src.stem}_{i}{src.suffix}"
        i += 1
    shutil.move(str(src), str(dest))
    return dest


def ingest_once(cfg: Config, conn: sqlite3.Connection, *,
                extractors: dict[str, Extractor]) -> IngestReport:
    report = IngestReport()
    for path in _iter_inbox(cfg):
        try:
            content_hash = file_content_hash(path)
            exists = conn.execute(
                "SELECT 1 FROM documents WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            if exists:
                report.skipped += 1
                continue

            ftype = detect_type(path)
            extractor = extractors.get(ftype)
            if extractor is None:
                raise ValueError(f"Không có extractor cho loại '{ftype}'")

            text = extractor(path)
            # Bug fix #2 + #3: Move FIRST (collision-safe), then INSERT + commit using
            # the actual final path. Move failure happens before any DB write → no phantom row.
            dest = _move_no_clobber(path, cfg.processed_dir)
            conn.execute(
                "INSERT INTO documents(content_hash, source_path, file_type, status, extracted_text) "
                "VALUES (?,?,?,?,?)",
                (content_hash, str(dest), ftype, "ingested", text),
            )
            conn.commit()
            report.ingested += 1
        except Exception as exc:  # cô lập lỗi: không chặn file khác
            report.failed += 1
            report.failed_files.append(path.name)
            print(f"[ingest] LỖI {path.name}: {exc}")
            # Bug fix #1 + #3: Wrap recovery move in its own try/except so a move
            # failure (e.g. FileExistsError on Windows) logs and continues, never
            # aborts the loop. Also uses _move_no_clobber for collision safety.
            try:
                _move_no_clobber(path, cfg.failed_dir)
            except Exception as move_exc:
                print(f"[ingest] Không thể move {path.name} vào _failed: {move_exc}")
    return report


def build_default_extractors(llm) -> dict[str, Extractor]:
    from ai_tutor.ingest.processors import (
        text_processor, pdf_processor, docx_processor,
        image_processor, video_processor,
    )

    def vision(p: Path) -> str:
        # Token-saving: chỉ chạy khi OCR cục bộ kém (image_processor quyết định).
        media = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return llm.vision(p.read_bytes(),
                          "Trích toàn bộ chữ/đề bài trong ảnh. Chỉ trả text.",
                          media_type=media)

    return {
        "text": text_processor.extract_text,
        "pdf": pdf_processor.extract_text,
        "docx": docx_processor.extract_text,
        "image": lambda p: image_processor.extract_text(
            p, ocr=image_processor.default_ocr, vision=vision),
        "video": lambda p: video_processor.extract_text(
            p, transcribe=video_processor.default_transcribe),
    }
