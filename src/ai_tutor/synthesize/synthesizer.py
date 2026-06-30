from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from ai_tutor.config import Config

_SYSTEM = (
    "Bạn là trợ giảng. Từ tài liệu của giáo viên dưới đây, hãy viết BẢN TỔNG HỢP "
    "kiến thức của bài bằng tiếng Việt, theo đúng cấu trúc markdown:\n"
    "# {Tên bài}\n## Tóm tắt lý thuyết\n## Công thức / Quy tắc chính\n"
    "## Ví dụ mẫu (kèm lời giải)\n## Lỗi thường gặp\n"
    "Chỉ dựa trên tài liệu được cung cấp, ngắn gọn, đúng trình độ học sinh."
)


def compute_source_hash(conn: sqlite3.Connection, lesson_id: int) -> str:
    rows = conn.execute(
        "SELECT content_hash FROM documents WHERE lesson_id=? ORDER BY content_hash",
        (lesson_id,),
    ).fetchall()
    joined = "\n".join(r["content_hash"] for r in rows)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def synthesize_lesson(conn: sqlite3.Connection, cfg: Config, claude,
                      lesson_id: int) -> Path | None:
    lesson = conn.execute(
        "SELECT mon, lop, chuong, bai, dir_path, source_hash FROM lessons WHERE id=?",
        (lesson_id,),
    ).fetchone()
    new_hash = compute_source_hash(conn, lesson_id)
    if lesson["source_hash"] == new_hash:
        return None  # cache: nguồn không đổi → không gọi Claude

    docs = conn.execute(
        "SELECT source_path, extracted_text FROM documents WHERE lesson_id=? ORDER BY id",
        (lesson_id,),
    ).fetchall()
    combined = "\n\n".join((d["extracted_text"] or "").strip() for d in docs)[:12000]
    header = f"{lesson['bai'] or 'Bài'} - {lesson['mon']} lớp {lesson['lop']}"
    md = claude.complete(
        system=_SYSTEM,
        user=f"Bài: {header}\n\n--- TÀI LIỆU ---\n{combined}",
        smart=True,
        max_tokens=1500,
    )

    dir_path = Path(lesson["dir_path"])
    dir_path.mkdir(parents=True, exist_ok=True)
    lesson_md = dir_path / "lesson.md"
    lesson_md.write_text(md, encoding="utf-8")

    skills = [r["name"] for r in conn.execute(
        "SELECT s.name FROM skills s JOIN lesson_skills ls ON ls.skill_id=s.id "
        "WHERE ls.lesson_id=?", (lesson_id,))]
    meta = {
        "mon": lesson["mon"], "lop": lesson["lop"],
        "chuong": lesson["chuong"], "bai": lesson["bai"],
        "ky_nang": skills,
        "nguon": [d["source_path"] for d in docs],
        "source_hash": new_hash,
    }
    (dir_path / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    conn.execute("UPDATE lessons SET source_hash=? WHERE id=?", (new_hash, lesson_id))
    conn.execute("UPDATE documents SET status='synthesized' WHERE lesson_id=?", (lesson_id,))
    conn.commit()
    return lesson_md
