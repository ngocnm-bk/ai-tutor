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
            # Giữ bản gốc: chuyển sang _processed thay vì xóa (Phase 1B sẽ archive vào kb/sources).
            # source_path ghi đích _processed để Phase 1B đọc đúng vị trí file sau khi move.
            dest = cfg.processed_dir / path.name
            conn.execute(
                "INSERT INTO documents(content_hash, source_path, file_type, status, extracted_text) "
                "VALUES (?,?,?,?,?)",
                (content_hash, str(dest), ftype, "ingested", text),
            )
            conn.commit()
            shutil.move(str(path), str(dest))
            report.ingested += 1
        except Exception as exc:  # cô lập lỗi: không chặn file khác
            report.failed += 1
            report.failed_files.append(path.name)
            print(f"[ingest] LỖI {path.name}: {exc}")
            shutil.move(str(path), str(cfg.failed_dir / path.name))
    return report


def build_default_extractors(claude) -> dict[str, Extractor]:
    from ai_tutor.ingest.processors import (
        text_processor, pdf_processor, docx_processor,
        image_processor, video_processor,
    )

    def vision(p: Path) -> str:
        # Token-saving: chỉ chạy khi OCR cục bộ kém (do image_processor quyết định).
        import base64
        data = base64.standard_b64encode(p.read_bytes()).decode()
        media = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        resp = claude._client.messages.create(
            model=claude._cheap_model, max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": media, "data": data}},
                {"type": "text", "text": "Trích toàn bộ chữ/đề bài trong ảnh. Chỉ trả text."},
            ]}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")

    return {
        "text": text_processor.extract_text,
        "pdf": pdf_processor.extract_text,
        "docx": docx_processor.extract_text,
        "image": lambda p: image_processor.extract_text(
            p, ocr=image_processor.default_ocr, vision=vision),
        "video": lambda p: video_processor.extract_text(
            p, transcribe=video_processor.default_transcribe),
    }
