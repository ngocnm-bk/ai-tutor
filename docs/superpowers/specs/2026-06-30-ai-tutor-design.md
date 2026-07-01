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

**Nguyên tắc xuyên suốt:** *Triển khai đơn giản, dễ làm, local-first, chỉ tốn phí cho LLM (nhà cung cấp đã chọn — mặc định Gemini; xem mục 12).*

### 1.1. Nguyên tắc tiết kiệm token (BẮT BUỘC khi thiết kế mọi khối)

1. **Ưu tiên Python, hạn chế gọi Claude.** Việc gì xử lý được bằng script Python thuần thì KHÔNG gọi Claude. Chỉ gọi Claude cho phần thật sự cần "hiểu/lập luận ngôn ngữ tự nhiên" (giải thích bài cho con, phân loại khi heuristic không chắc, đọc ảnh khi OCR cục bộ kém). Mặc định mỗi khi định gọi Claude, phải tự hỏi: *"Có làm được bằng Python không?"*

   Việc làm bằng Python thuần (không Claude): đọc PDF/Word/text, transcribe video (faster-whisper cục bộ), OCR cục bộ chữ in, băm/chống trùng, định tuyến file, ghép `lesson.md`, truy hồi từ khóa (Phase 1), embeddings + tìm vector (Phase 2, cục bộ), lập lịch spaced repetition (SM-2), chấm câu trả lời có đáp án cố định, tổng hợp số liệu báo cáo.

2. **Khi buộc phải gọi Claude, tối ưu input/output triệt để:**
   - **Input gọn:** chỉ gửi đoạn nội dung liên quan đã truy hồi (không gửi cả tài liệu); chuẩn hóa/cắt khoảng trắng, bỏ boilerplate trước khi gửi.
   - **Prompt caching:** cache phần lặp lại (system prompt, ngữ cảnh KB dùng nhiều lần) để không trả token nhiều lần.
   - **Gộp batch:** phân loại nhiều tài liệu ngắn trong 1 lần gọi thay vì nhiều lần.
   - **Chọn model theo độ khó:** **Claude Haiku** (rẻ) cho việc đơn giản (phân loại, trích xuất); model lớn chỉ cho lập luận dạy học.
   - **Giới hạn output:** đặt `max_tokens` hợp lý, dùng structured output, yêu cầu trả lời ngắn gọn đúng nhu cầu.
   - **Nén trước khi lưu/gửi lại:** transcript dài được tóm tắt/chuẩn hóa cục bộ trước khi đưa vào prompt sau này.

## 2. Đầu vào (tài liệu giáo viên)

Tỉ lệ ước lượng các dạng tài liệu:

| Dạng | Tỉ lệ | Cách xử lý |
|---|---|---|
| Video bài giảng | **60%** | `ffmpeg` tách audio → **faster-whisper** transcribe tiếng Việt. **Chỉ cần nghe lời giảng, KHÔNG cần OCR khung hình.** |
| Ảnh chụp (đề bài, trang sách, bài viết tay) | 20% | **OCR cục bộ trước** (Tesseract/PaddleOCR) cho chữ in; **chỉ gọi Claude vision khi OCR cục bộ kém** (chữ viết tay, công thức khó). Tiết kiệm token. |
| PDF/Word/văn bản số | 15% | `pypdf` / `python-docx` đọc text trực tiếp |
| Tin nhắn chữ Zalo | 5% | Đọc thẳng |

Phần xử lý "nặng" duy nhất là **chuyển giọng nói tiếng Việt → văn bản** cho video.

## 3. Kiến trúc tổng thể

Hệ thống gồm **6 khối độc lập**, mỗi khối một nhiệm vụ rõ ràng, giao tiếp qua interface rõ ràng, test riêng được:

```
[Bỏ file vào inbox/]  (ảnh, pdf, video, text)
        │
        ▼
┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌─────────────────────┐
│ INGEST   │→ │ CLASSIFY  │→ │ SYNTHESIZE    │→ │ KNOWLEDGE BASE      │
│ xử lý    │   │ heuristic │   │ gộp tài liệu  │   │ kb/ markdown+SQLite │
│ từng loại│   │ Python +  │   │ 1 bài → Claude│   │ [+ ChromaDB P2]     │
│ file     │   │ Claude khi│   │ tạo lesson.md │   │                     │
│          │   │ cần       │   │ (1 lần/bài,   │   │                     │
│          │   │ lớp/môn/  │   │  có cache)    │   └──────────┬──────────┘
│          │   │ chương/bài│   └──────────────┘              │ retrieve
└──────────┘   └──────────┘                                  ▼
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

Bảy khối: **Ingest · Classify · Synthesize · Knowledge Base · Tutor · Adaptive · Auto-collect**.

## 4. Cấu trúc Knowledge Base (theo chương/bài/kỹ năng — KHÔNG theo ngày)

```
kb/
  toan/
    lop3/
      chuong-02-phep-nhan/
        bai-05-bang-nhan-6/
          lesson.md      # BẢN TỔNG HỢP KIẾN THỨC do Claude tạo (xem mục 6.5)
          meta.json      # {mon, lop, chuong, bai, ky_nang[], nguon[], source_hash}
          sources/       # tài liệu gốc + transcript thô (raw, để đối chiếu)
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

## 6. Classify — phân loại (heuristic Python trước, Claude sau)

- **Bước 1 — heuristic Python (không tốn token):** suy luận `lop/mon/chuong/bai` từ tên file, tên thư mục nguồn, và từ khóa rõ ràng trong text ("Bài 5", "Chương 2", "Unit 3"…). Nếu đủ chắc → ghi KB luôn, KHÔNG gọi Claude.
- **Bước 2 — Claude (chỉ khi heuristic không chắc):** gửi text đã cắt gọn → Claude trả metadata `lop/mon/chuong/bai/ky_nang[]` qua **structured output (JSON schema)**. Dùng **Claude Haiku** (rẻ). **Gộp nhiều tài liệu ngắn trong 1 lần gọi** khi có thể.
- Kết quả ghi vào KB (`kb/...` + bảng SQLite).

## 6.5. Synthesize — tổng hợp kiến thức theo bài

Khối này biến tài liệu thô của một bài thành **một bản tổng hợp kiến thức có cấu trúc** (`lesson.md`).

- **Khi nào chạy:** khi một bài đã gom đủ tài liệu (1+ nguồn đã classify). Gọi Claude **1 lần/bài**.
- **Đầu vào (đã cắt gọn để tiết kiệm token):** text đã trích từ các nguồn của bài (transcript video, text ảnh/pdf), chuẩn hóa bằng Python trước khi gửi.
- **Đầu ra — `lesson.md` theo template cố định:**
  ```
  # {Bài} ({Môn} lớp {n})
  ## Tóm tắt lý thuyết
  ## Công thức / Quy tắc chính
  ## Ví dụ mẫu (kèm lời giải)
  ## Lỗi thường gặp
  ## Nguồn
  ```
- **Cache / idempotent:** lưu `source_hash` (băm tổng hợp các nguồn) trong `meta.json`. Chỉ **tạo lại khi nguồn thay đổi** (thêm tài liệu mới cho bài). Không gọi Claude lại nếu nguồn không đổi.
- **Vì sao hợp nguyên tắc tiết kiệm token (amortize):** tốn token **1 lần/bài**, nhưng:
  1. Mỗi câu hỏi sau chỉ gửi `lesson.md` **ngắn gọn** cho Tutor, thay vì transcript dài → rẻ hơn nhiều về sau.
  2. Chất lượng trả lời cao hơn (nội dung sạch, có cấu trúc).
  3. `lesson.md` đồng thời là **"ghi chú bài học"** để con tự ôn.
- **Transcript thô vẫn giữ** trong `sources/` để đối chiếu khi cần.
- **Tổng hợp theo CHỦ ĐỀ/kỹ năng (xuyên nhiều bài):** để Phase sau, sinh **theo yêu cầu** (khi bấm "ôn chủ đề X") — không tạo sẵn để khỏi tốn token thừa.

## 7. AI Tutor (Telegram) — RAG có ngữ cảnh

- Con nhắn câu hỏi (gõ chữ **hoặc gửi ảnh bài**) qua **Telegram bot**.
- Bot xác định lớp/môn/bài liên quan → lấy nội dung KB → đưa cho Claude kèm **system prompt ràng buộc**:

  > *"Chỉ trả lời dựa trên tài liệu của cô giáo dưới đây. Nếu không có trong tài liệu, nói rõ là chưa có và khuyên hỏi cô. Giải thích theo trình độ lớp {3/6}."*

- Mục tiêu: **chống bịa thông tin**, giữ **nhất quán với cách dạy trên lớp**.
- Phân biệt 2 bạn qua **Telegram user ID** (ánh xạ trong bảng `students`).
- Mỗi lượt hỏi/đáp ghi vào `qa_log`.
- **Tiết kiệm token (xem mục 1.1):** chỉ đưa vào prompt các đoạn KB đã truy hồi (không nhồi cả bài), dùng **prompt caching** cho system prompt + ngữ cảnh bài lặp lại, đặt `max_tokens` hợp lý. Truy hồi (Phase 1 từ khóa / Phase 2 vector) làm bằng Python cục bộ — không tốn token.

**Lý do chọn Telegram thay vì Zalo:** Zalo không có API bot chính thức cho tài khoản cá nhân (chỉ có Official Account cần đăng ký doanh nghiệp, hoặc thư viện không chính thức dễ bị khóa tài khoản). Telegram có API bot chính thức, miễn phí, dễ làm, đầy đủ ảnh/file/audio. Trải nghiệm với con gần như y hệt.

## 8. Phase 1 (MVP) — truy hồi chưa cần vector

- KB lưu dạng markdown (`lesson.md` đã tổng hợp ở mục 6.5) + chỉ mục SQLite.
- Bot chọn bài liên quan bằng lớp/môn + từ khóa/chương-bài (đơn giản), đưa **`lesson.md` tổng hợp** (ngắn gọn) cho Claude.
- **Đã bao gồm khối Synthesize** (tổng hợp theo bài) — đây là phần lõi của MVP, không để sau.
- **Đây là lát cắt chạy được, dùng thật.**

## 9. Phase 2 — RAG ngữ nghĩa

- Thêm **embeddings** (`sentence-transformers` đa ngôn ngữ, chạy cục bộ, miễn phí) + **ChromaDB** (vector store cục bộ).
- Bot truy hồi đoạn nội dung liên quan theo ngữ nghĩa → chính xác hơn khi tài liệu nhiều.

## 10. Phase 3 — Học thích ứng & báo cáo phụ huynh

- Phát hiện câu con làm sai → lưu `mistakes` (gắn kỹ năng yếu). Với bài có **đáp án cố định** (Toán), chấm bằng **Python** (so khớp), không tốn token; chỉ dùng Claude cho câu trả lời tự luận.
- Claude sinh **bài luyện bổ sung** đúng kỹ năng yếu (gọi gọn, có thể gộp nhiều câu/1 lần).
- **Spaced repetition** (thuật toán kiểu SM-2): toàn bộ tính toán lịch ôn bằng **Python**, không gọi Claude; bot chủ động nhắn.
- **Báo cáo tiến bộ:** tổng hợp số liệu bằng **Python**; chỉ (tùy chọn) dùng Claude viết phần nhận xét ngắn. Gửi phụ huynh qua Telegram (hằng tuần).

## 11. Phase 4 — Tự thu thập

- **Google Drive** sync (API chính thức).
- Import dữ liệu **Zalo export**.
- Giảm thao tác thủ công bỏ file vào `inbox/`.

## 12. Công nghệ

| Thành phần | Lựa chọn | Phí |
|---|---|---|
| Ngôn ngữ | Python 3.11+ | — |
| Bot | `python-telegram-bot` | miễn phí |
| "Não" AI (tutor, phân loại khó, đọc ảnh khó) | **LLM đa nhà cung cấp** qua SDK `openai` (OpenAI-compatible): Gemini (mặc định) / OpenAI / Grok / Claude — model rẻ cho việc đơn giản, model mạnh cho dạy học | **trả phí — gọi tối thiểu** |
| OCR cục bộ (chữ in) | Tesseract / PaddleOCR | miễn phí |
| Transcribe video | `faster-whisper` (cục bộ) + ffmpeg | miễn phí |
| Đọc PDF/Word | `pypdf` / `python-docx` | miễn phí |
| Embeddings (Phase 2) | `sentence-transformers` (cục bộ) | miễn phí |
| Vector store (Phase 2) | `chromadb` (cục bộ) | miễn phí |
| CSDL | SQLite (thư viện chuẩn) | miễn phí |
| Cấu hình | `.env` (`LLM_PROVIDER` + khóa nhà cung cấp, token Telegram) | — |

**Local-first:** chỉ LLM (nhà cung cấp đã chọn) tốn phí; mọi thứ còn lại chạy cục bộ trên máy người dùng (Windows).

**Đa nhà cung cấp LLM (OpenAI-compatible):** đổi nhà = đổi `LLM_PROVIDER` trong `.env`. Wrapper `src/ai_tutor/llm.py` (`LLMClient`) giữ interface `complete`/`complete_json` (JSON mode)/`vision`; registry `src/ai_tutor/providers.py`:

| Provider | base_url | model rẻ | model mạnh | key env |
|---|---|---|---|---|
| **gemini** (mặc định) | `.../v1beta/openai/` | `gemini-2.5-flash` | `gemini-2.5-pro` | `GEMINI_API_KEY` |
| openai | (mặc định) | `gpt-4o-mini` | `gpt-4o` | `OPENAI_API_KEY` |
| grok | `https://api.x.ai/v1` | `grok-3-mini` | `grok-3` | `XAI_API_KEY` |
| claude | `https://api.anthropic.com/v1/` | `claude-haiku-4-5-20251001` | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |

Model đều override được qua `LLM_CHEAP_MODEL`/`LLM_SMART_MODEL`/`LLM_BASE_URL`.

## 13. Cấu trúc mã nguồn

```
ai-tutor/
  inbox/                  # bỏ file vào đây (thu thập thủ công cho MVP)
    _failed/              # file xử lý lỗi
  kb/                     # knowledge base (markdown + meta.json)
  data/                   # sqlite db, chroma (Phase 2)
  src/ai_tutor/
    ingest/               # watcher + processors (image/pdf/docx/video/text)
    classify/             # heuristic Python + Claude classifier (structured output)
    synthesize/           # tổng hợp 1 bài → lesson.md (1 lần/bài, có cache)
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
| **1 — MVP** | Ingest + Classify + **Synthesize (tổng hợp theo bài)** + KB markdown + Tutor trả lời theo bài (chưa vector) | **Dùng thật được** |
| **2** | Embeddings + ChromaDB → truy hồi ngữ nghĩa; tổng hợp **theo chủ đề** (theo yêu cầu) | Tìm bài chuẩn hơn, ôn theo chủ đề |
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
5. Stack **Python local-first**; chỉ LLM (nhà cung cấp đã chọn) tốn phí. LLM đa nhà cung cấp qua SDK `openai` (mặc định Gemini).
6. Xây theo lát cắt: **Phase 0 → 1 trước**, RAG vector và học thích ứng làm sau.
7. Thu thập tự động (Zalo/Drive) để **Phase 4**; MVP nạp file thủ công vào `inbox/`.
8. **Tiết kiệm token là nguyên tắc bắt buộc (mục 1.1):** ưu tiên Python; chỉ gọi Claude khi thật cần; khi gọi thì tối ưu input/output (cắt gọn, prompt caching, gộp batch, Haiku cho việc rẻ, giới hạn output).
9. **Tổng hợp kiến thức theo BÀI (mục 6.5) nằm trong MVP:** Claude tạo `lesson.md` có cấu trúc 1 lần/bài, có cache theo `source_hash` — vừa cho "ghi chú bài học", vừa tiết kiệm token về dài hạn (amortize). Tổng hợp theo **chủ đề** để Phase 2, sinh theo yêu cầu.
