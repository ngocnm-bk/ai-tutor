# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Trạng thái:** Greenfield — thiết kế đã chốt, code chưa được scaffold. Đang ở **Phase 0**.
> Tài liệu thiết kế đầy đủ (nguồn sự thật): [docs/superpowers/specs/2026-06-30-ai-tutor-design.md](docs/superpowers/specs/2026-06-30-ai-tutor-design.md).
> Khi thực tế code khác tài liệu này, cập nhật lại CLAUDE.md.

## Hệ thống này là gì

AI Tutor cá nhân/gia đình cho 2 con (**lớp 3** và **lớp 6**, môn **Toán** + **Tiếng Anh**). Trả lời **chỉ dựa trên tài liệu của giáo viên** (RAG có ngữ cảnh), để nhất quán với cách dạy trên lớp. Tương tác qua **Telegram bot**.

Nguyên tắc: **local-first, đơn giản, chỉ Claude tốn phí** — mọi xử lý khác chạy cục bộ trên máy Windows của người dùng.

## ⚠️ Nguyên tắc tiết kiệm token (BẮT BUỘC — áp dụng khi viết MỌI code)

1. **Ưu tiên Python, hạn chế gọi Claude.** Việc gì làm được bằng script Python thuần thì KHÔNG gọi Claude. Trước mỗi lần định gọi Claude, tự hỏi *"có làm được bằng Python không?"*. Làm bằng Python: đọc PDF/Word/text, transcribe (faster-whisper cục bộ), OCR chữ in cục bộ, băm/chống trùng, định tuyến file, ghép `lesson.md`, truy hồi từ khóa/vector cục bộ, lịch spaced repetition (SM-2), chấm đáp án cố định, tổng hợp số liệu báo cáo.
2. **Khi buộc gọi Claude, tối ưu input/output:** chỉ gửi đoạn KB đã truy hồi (không gửi cả tài liệu) + cắt gọn boilerplate; **prompt caching** cho system prompt/ngữ cảnh lặp lại; **gộp batch** nhiều tài liệu ngắn/1 lần gọi; **Claude Haiku** cho việc đơn giản (phân loại, trích xuất), model lớn chỉ cho lập luận dạy; đặt `max_tokens` hợp lý + structured output để output ngắn.

Chi tiết: mục 1.1 trong tài liệu thiết kế.

## Kiến trúc (6 khối độc lập)

Luồng: `inbox/ → INGEST → CLASSIFY → KNOWLEDGE BASE → TUTOR (Telegram) → [Phase 3] ADAPTIVE`

| Khối | Thư mục | Nhiệm vụ |
|---|---|---|
| **Ingest** | `src/ai_tutor/ingest/` | Xử lý file theo loại: ảnh→**OCR cục bộ trước, Claude vision chỉ khi kém**, pdf/docx→text (Python), video→`ffmpeg`+**faster-whisper** (cục bộ), text→thẳng. Idempotent (hash chống trùng), lỗi đẩy vào `inbox/_failed/` không chặn file khác. |
| **Classify** | `src/ai_tutor/classify/` | **Heuristic Python trước** (tên file/thư mục/từ khóa chương-bài); **chỉ gọi Claude (Haiku, structured output, gộp batch) khi không chắc**. Gắn `lop/mon/chuong/bai/ky_nang`. |
| **Knowledge Base** | `src/ai_tutor/kb/` + `kb/` | Lưu bài theo **chương/bài/kỹ năng** (KHÔNG theo ngày): markdown + `meta.json`, chỉ mục trong SQLite. Phase 2 thêm ChromaDB. |
| **Tutor** | `src/ai_tutor/tutor/` | Telegram bot. Truy hồi nội dung KB → Claude trả lời với system prompt ràng buộc "chỉ dùng tài liệu cô; không có thì nói chưa có". Phân biệt 2 bạn qua Telegram user ID. Ghi `qa_log`. |
| **Adaptive** *(Phase 3)* | `src/ai_tutor/adaptive/` | Ghi câu sai → sinh bài luyện → spaced repetition (kiểu SM-2) → báo cáo phụ huynh. |
| **Auto-collect** *(Phase 4)* | — | Google Drive sync, import Zalo export. |

**Quan trọng khi đọc/sửa code:** mỗi khối là một unit có biên rõ ràng, giao tiếp qua interface rõ, **test độc lập được**. Giữ file nhỏ, một nhiệm vụ. Đừng để Tutor biết chi tiết bên trong Ingest, v.v.

## Knowledge Base — bố cục

```
kb/<mon>/lop<n>/chuong-XX-.../bai-YY-.../
    lesson.md     # nội dung bài đã chuẩn hóa
    meta.json     # {mon, lop, chuong, bai, ky_nang[], nguon[]}
    sources/      # file gốc + transcript
```
SQLite (trong `data/`) giữ dữ liệu động/chỉ mục: `documents, lessons, skills, students, qa_log, mistakes, reviews`.

## Stack & lệnh thường dùng

> Project dùng **Python 3.11+**. Quản lý môi trường bằng venv. (Các lệnh dưới là quy ước đã chốt; cập nhật khi `pyproject.toml`/scripts thực tế được tạo.)

```bash
# Thiết lập môi trường
python -m venv .venv
.venv\Scripts\activate          # PowerShell/Windows
pip install -e .                 # cài theo pyproject.toml

# Chạy
python scripts/ingest_once.py    # quét inbox/ → KB (xử lý 1 lượt)
python scripts/run_bot.py        # chạy Telegram bot (AI Tutor)

# Test
pytest                           # toàn bộ
pytest tests/test_ingest.py      # 1 file
pytest tests/test_ingest.py::test_pdf -q   # 1 test
```

**Phụ thuộc ngoài:** cần **ffmpeg** cài sẵn trên máy (tách audio cho video).

## Thư viện chính

`python-telegram-bot` · `anthropic` (Claude) · `faster-whisper` + ffmpeg · OCR cục bộ (Tesseract/PaddleOCR) · `pypdf` / `python-docx` · `sentence-transformers` + `chromadb` (Phase 2) · `sqlite3` (stdlib).

## Cấu hình & bí mật

`.env` (xem `.env.example`): `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`. Nạp qua `src/ai_tutor/config.py`. **Không commit `.env`.**

## Mô hình Claude

Gọi Claude **tối thiểu** (xem nguyên tắc tiết kiệm token ở trên). Chọn model theo độ khó: **Haiku** cho việc đơn giản (phân loại, trích xuất), model lớn mới nhất cho lập luận dạy học. Ảnh: **OCR cục bộ trước**, chỉ dùng **Claude vision** khi OCR kém (chữ viết tay/công thức). Phân loại dùng **structured output** + **gộp batch**. Dùng **prompt caching** cho phần lặp lại. Trong unit test, **mock Claude API** (không gọi mạng).

## Quy ước test

Mỗi processor/classifier/retriever test riêng bằng dữ liệu mẫu nhỏ trong `tests/`. Pipeline cô lập lỗi: một file hỏng không được làm sập cả lượt ingest.

## Lộ trình (đang ở Phase 0)

0. Khung repo, config, schema SQLite, client Claude, bot Telegram "echo".
1. **MVP:** Ingest + Classify + KB markdown + Tutor trả lời theo bài (chưa vector). ← *mục tiêu chạy thật đầu tiên*
2. RAG: embeddings + ChromaDB.
3. Adaptive: spaced repetition + báo cáo phụ huynh.
4. Auto-collect: Google Drive + Zalo export.

## Vì sao Telegram (không phải Zalo)

Zalo không có API bot chính thức cho tài khoản cá nhân (chỉ Official Account cho doanh nghiệp, hoặc thư viện không chính thức dễ bị khóa tài khoản). Telegram: API bot chính thức, miễn phí, đầy đủ ảnh/file/audio. Đây là quyết định đã chốt — đừng đề xuất lại Zalo bot trừ khi người dùng yêu cầu.
