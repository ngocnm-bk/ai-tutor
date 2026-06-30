# Thiết kế hệ thống AI Tutor (cá nhân / gia đình)

- **Ngày:** 2026-06-30
- **Trạng thái:** Đã được người dùng phê duyệt (brainstorming)
- **Phạm vi tài liệu này:** Toàn bộ tầm nhìn + lộ trình; trọng tâm triển khai trước mắt là **Phase 0 → Phase 1 (MVP)**.

## 1. Bối cảnh & mục tiêu

Xây dựng một AI Tutor cá nhân cho gia đình, giúp 2 con học tập dựa **đúng trên tài liệu của giáo viên** (nhất quán với cách dạy trên lớp), và về lâu dài hỗ trợ học thích ứng + báo cáo cho phụ huynh.

**Người dùng:** cá nhân/gia đình (không đa người dùng, không cần đăng nhập phức tạp, không cần mở rộng quy mô).

**Học sinh:**
- Bạn A — **lớp 3**
- Bạn B — **lớp 6**

**Môn ưu tiên trước:** **Toán** và **Tiếng Anh**.

**Nguyên tắc xuyên suốt:** *Triển khai đơn giản, dễ làm, local-first, chỉ tốn phí cho Claude.*

## 2. Đầu vào (tài liệu giáo viên)

Tỉ lệ ước lượng các dạng tài liệu:

| Dạng | Tỉ lệ | Cách xử lý |
|---|---|---|
| Video bài giảng | **60%** | `ffmpeg` tách audio → **faster-whisper** transcribe tiếng Việt. **Chỉ cần nghe lời giảng, KHÔNG cần OCR khung hình.** |
| Ảnh chụp (đề bài, trang sách, bài viết tay) | 20% | Gửi thẳng **Claude vision** → trích text (không cần engine OCR riêng) |
| PDF/Word/văn bản số | 15% | `pypdf` / `python-docx` đọc text trực tiếp |
| Tin nhắn chữ Zalo | 5% | Đọc thẳng |

Phần xử lý "nặng" duy nhất là **chuyển giọng nói tiếng Việt → văn bản** cho video.

## 3. Kiến trúc tổng thể

Hệ thống gồm **6 khối độc lập**, mỗi khối một nhiệm vụ rõ ràng, giao tiếp qua interface rõ ràng, test riêng được:

```
[Bỏ file vào inbox/]  (ảnh, pdf, video, text)
        │
        ▼
┌──────────┐   ┌──────────┐   ┌───────────────────────────┐
│ INGEST   │→ │ CLASSIFY  │→ │ KNOWLEDGE BASE             │
│ xử lý    │   │ Claude gắn│   │ kb/ markdown + SQLite      │
│ từng loại│   │ lớp/môn/  │   │ [+ ChromaDB ở Phase 2]     │
│ file     │   │ chương/   │   │                            │
│          │   │ bài/kỹ năng│  └─────────────┬─────────────┘
└──────────┘   └──────────┘                 │ retrieve
                                            ▼
   con nhắn Telegram ───────────→ ┌──────────────────────────┐
                                  │ AI TUTOR (Telegram bot)  │
                                  │ lấy nội dung bài →       │
                                  │ Claude trả lời "chỉ dựa  │
                                  │ trên tài liệu cô" → log  │
                                  └────────────┬─────────────┘
                                               ▼
   [Phase 3] ─────────────────→  ┌──────────────────────────┐
                                  │ ADAPTIVE: ghi câu sai →  │
                                  │ tạo bài luyện → spaced   │
                                  │ repetition → báo cáo PH  │
                                  └──────────────────────────┘
```

Sáu khối: **Ingest · Classify · Knowledge Base · Tutor · Adaptive · Auto-collect**.

## 4. Cấu trúc Knowledge Base (theo chương/bài/kỹ năng — KHÔNG theo ngày)

```
kb/
  toan/
    lop3/
      chuong-02-phep-nhan/
        bai-05-bang-nhan-6/
          lesson.md      # nội dung bài đã chuẩn hóa (gộp từ video/ảnh/pdf)
          meta.json      # {mon, lop, chuong, bai, ky_nang[], nguon[]}
          sources/       # trỏ tới file gốc + transcript
    lop6/
  tieng-anh/
    lop3/ ...
    lop6/ ...
```

`meta.json` (ví dụ):
```json
{
  "mon": "toan",
  "lop": 3,
  "chuong": "Chương 2 - Phép nhân",
  "bai": "Bài 5 - Bảng nhân 6",
  "ky_nang": ["bang-nhan-6", "nhan-trong-pham-vi-100"],
  "nguon": ["sources/video-2026-03-01.mp4", "sources/transcript.txt"]
}
```

### Lược đồ SQLite (chỉ mục + dữ liệu động)

| Bảng | Mục đích |
|---|---|
| `documents` | mỗi file gốc đã nạp (hash, loại, đường dẫn, trạng thái) |
| `lessons` | mỗi bài học trong KB (trỏ tới thư mục `kb/...`) |
| `skills` | danh mục kỹ năng (gắn với bài) |
| `students` | 2 học sinh, ánh xạ Telegram user ID → lớp |
| `qa_log` | lịch sử hỏi/đáp của từng học sinh |
| `mistakes` | câu trả lời sai (Phase 3) |
| `reviews` | lịch ôn tập spaced repetition (Phase 3) |

## 5. Ingest — xử lý đầu vào

- **Idempotent:** băm (hash) nội dung file để bỏ qua file trùng.
- **Cô lập lỗi:** một file lỗi đẩy vào `inbox/_failed/` kèm log; các file khác vẫn chạy tiếp (không chặn nhau).
- Mỗi processor (image / pdf / docx / video / text) là một unit riêng, nhận file → trả về text + metadata thô. Test riêng từng processor bằng file mẫu.

## 6. Classify — phân loại bằng Claude

- Nhận text thô từ Ingest → Claude trả về metadata có cấu trúc: `lop`, `mon`, `chuong`, `bai`, `ky_nang[]`.
- Dùng structured output (JSON schema) để ép Claude trả đúng định dạng.
- Kết quả ghi vào KB (`kb/...` + bảng SQLite).

## 7. AI Tutor (Telegram) — RAG có ngữ cảnh

- Con nhắn câu hỏi (gõ chữ **hoặc gửi ảnh bài**) qua **Telegram bot**.
- Bot xác định lớp/môn/bài liên quan → lấy nội dung KB → đưa cho Claude kèm **system prompt ràng buộc**:

  > *"Chỉ trả lời dựa trên tài liệu của cô giáo dưới đây. Nếu không có trong tài liệu, nói rõ là chưa có và khuyên hỏi cô. Giải thích theo trình độ lớp {3/6}."*

- Mục tiêu: **chống bịa thông tin**, giữ **nhất quán với cách dạy trên lớp**.
- Phân biệt 2 bạn qua **Telegram user ID** (ánh xạ trong bảng `students`).
- Mỗi lượt hỏi/đáp ghi vào `qa_log`.

**Lý do chọn Telegram thay vì Zalo:** Zalo không có API bot chính thức cho tài khoản cá nhân (chỉ có Official Account cần đăng ký doanh nghiệp, hoặc thư viện không chính thức dễ bị khóa tài khoản). Telegram có API bot chính thức, miễn phí, dễ làm, đầy đủ ảnh/file/audio. Trải nghiệm với con gần như y hệt.

## 8. Phase 1 (MVP) — truy hồi chưa cần vector

- KB lưu dạng markdown + chỉ mục SQLite.
- Bot chọn bài liên quan bằng lớp/môn + từ khóa/chương-bài (đơn giản), đưa nội dung cho Claude.
- **Đây là lát cắt chạy được, dùng thật.**

## 9. Phase 2 — RAG ngữ nghĩa

- Thêm **embeddings** (`sentence-transformers` đa ngôn ngữ, chạy cục bộ, miễn phí) + **ChromaDB** (vector store cục bộ).
- Bot truy hồi đoạn nội dung liên quan theo ngữ nghĩa → chính xác hơn khi tài liệu nhiều.

## 10. Phase 3 — Học thích ứng & báo cáo phụ huynh

- Phát hiện câu con làm sai → lưu `mistakes` (gắn kỹ năng yếu).
- Claude tự sinh **bài luyện bổ sung** đúng kỹ năng yếu.
- **Spaced repetition** (thuật toán kiểu SM-2): lên lịch nhắc ôn; bot chủ động nhắn.
- **Báo cáo tiến bộ** gửi cho phụ huynh qua Telegram (hằng tuần).

## 11. Phase 4 — Tự thu thập

- **Google Drive** sync (API chính thức).
- Import dữ liệu **Zalo export**.
- Giảm thao tác thủ công bỏ file vào `inbox/`.

## 12. Công nghệ

| Thành phần | Lựa chọn | Phí |
|---|---|---|
| Ngôn ngữ | Python 3.11+ | — |
| Bot | `python-telegram-bot` | miễn phí |
| "Não" AI (tutor, phân loại, đọc ảnh) | `anthropic` SDK — Claude | **trả phí** |
| Transcribe video | `faster-whisper` (cục bộ) + ffmpeg | miễn phí |
| Đọc PDF/Word | `pypdf` / `python-docx` | miễn phí |
| Embeddings (Phase 2) | `sentence-transformers` (cục bộ) | miễn phí |
| Vector store (Phase 2) | `chromadb` (cục bộ) | miễn phí |
| CSDL | SQLite (thư viện chuẩn) | miễn phí |
| Cấu hình | `.env` (khóa Claude, token Telegram) | — |

**Local-first:** chỉ Claude tốn phí; mọi thứ còn lại chạy cục bộ trên máy người dùng (Windows).

## 13. Cấu trúc mã nguồn

```
ai-tutor/
  inbox/                  # bỏ file vào đây (thu thập thủ công cho MVP)
    _failed/              # file xử lý lỗi
  kb/                     # knowledge base (markdown + meta.json)
  data/                   # sqlite db, chroma (Phase 2)
  src/ai_tutor/
    ingest/               # watcher + processors (image/pdf/docx/video/text)
    classify/             # Claude classifier (structured output)
    kb/                   # đọc/ghi KB, retrieval
    tutor/                # telegram bot + RAG prompt
    adaptive/             # Phase 3
    config.py             # nạp .env
  scripts/                # run_bot.py, ingest_once.py
  tests/                  # test từng processor/classifier/retriever (mock Claude)
  .env.example
  pyproject.toml
  CLAUDE.md
```

## 14. Lộ trình

| Phase | Nội dung | Kết quả |
|---|---|---|
| **0** | Khung repo, config, schema SQLite, client Claude, bot Telegram "echo" | Bot trả lời được |
| **1 — MVP** | Ingest (ảnh/pdf/text/video) + Classify + KB markdown + Tutor trả lời theo bài (chưa vector) | **Dùng thật được** |
| **2** | Embeddings + ChromaDB → truy hồi ngữ nghĩa | Tìm bài chuẩn hơn |
| **3** | Học thích ứng + spaced repetition + báo cáo phụ huynh | Đủ tính năng |
| **4** | Google Drive sync, import Zalo export | Bớt thủ công |

## 15. Kiểm thử & xử lý lỗi

- Mỗi processor cô lập, idempotent; test bằng file mẫu nhỏ.
- Classifier test với transcript cố định; **mock Claude API** trong unit test (không gọi mạng).
- Retriever test với KB mẫu.
- File lỗi không chặn pipeline; ghi log rõ ràng vào `inbox/_failed/`.

## 16. Quyết định đã chốt (để khỏi bàn lại)

1. Cá nhân/gia đình, 2 học sinh (lớp 3 & lớp 6), môn Toán + Tiếng Anh trước.
2. Giao diện: **Telegram bot** (không Zalo bot — lý do ở mục 7).
3. Video chỉ cần **transcribe audio**, không OCR khung hình.
4. Ảnh dùng **Claude vision**, không cần engine OCR riêng.
5. Stack **Python local-first**; chỉ Claude tốn phí.
6. Xây theo lát cắt: **Phase 0 → 1 trước**, RAG vector và học thích ứng làm sau.
7. Thu thập tự động (Zalo/Drive) để **Phase 4**; MVP nạp file thủ công vào `inbox/`.
