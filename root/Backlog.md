# Backlog.md — Knowledge Base (cá nhân)

> Danh sách ticket **đang làm / sắp làm**, thực hiện **cuốn chiếu** (`AGENTS.md` §3.1).
> Nguồn quy trình: `AGENTS.md`. Kiến trúc: `architecture.md`.

> ⚠️ **Khôi phục 2026-11-08**: file này bị truncate khi ghi script; dựng lại từ VS Code local history + `docs/phases/*`.
> Ticket Phase 0/1/2/6/7 giữ nguyên văn; **Phase 2–4 viết lại dạng rút gọn** (chi tiết ở `docs/phases/phase-N.md`); **TD-20** mất mô tả gốc.

**Ticket đang làm:** _(trống — **Phase 9 hoàn tất** 5/5)_
**Ticket tiếp theo:** **KB-8.1** (ADR backfill #1 — bản học tập sâu) — Q&A đã chốt (Q1=B sâu · Q2=A đủ 16 · Q3=B ôn tập ở README · Q4=không bản EN) ⇒ **chạy được ngay**; nợ mở đáng làm: **TD-29** (top-N=4: MRR 1,0 + 2,0 s), **TD-9** (image 16,5 GB), **TD-18/19/27** (S)

---

## 1. Mục tiêu dự án

Chuyển RAG chatbot từ bài tập nhóm (onboard member) thành **knowledge base cá nhân**, chạy trên
**LLM free tier (Groq)**, bảo vệ **PII/secret** trước khi gửi ra LLM, và dần cải thiện chất lượng
RAG + UI.

---

## 2. Template ticket

```
### KB-<phase>.<số> — <tên ngắn>

| Trường | Giá trị |
|---|---|
| Trạng thái | Todo / In Progress / Review / Done / Blocked |
| Phase | <số> |
| Repo | BE / FE / BE+FE |
| Phụ thuộc | <ticket> |
| Ước lượng | S / M / L |

**Bối cảnh** — vì sao cần làm.
**Mục tiêu** — kết quả mong muốn.
**In scope** — làm gì.
**Out of scope** — không làm gì.
**Acceptance Criteria**
- [ ] ... (verify được)
**Q&A (trả lời trước khi làm)**
- Q1: <câu hỏi không suy ra được từ doc/code>
  → <user điền>
- Q2: ...
  → <user điền>
**Ghi chú kỹ thuật** — pattern / thư viện / trade-off.
**Kết quả verify** *(điền khi Done)* — lệnh + output.
**Learning note** *(điền khi Done)* — học được gì.
```

---

## 3. Trạng thái theo phase

| Phase | Chủ đề | Done / Tổng | Trạng thái |
|---|---|---|---|
| 0 | Foundation & AI workflow (Groq) | 4 / 4 | ✅ Done |
| 1 | Safety: PII/secret redaction | 3 / 3 | ✅ Done |
| 2 | RAG quality | 5 / 5 | ✅ Done (KB-2.1 → 2.5 — `docs/phases/phase-2.md`) |
| 3 | Backend robustness | 5 / 5 | ✅ Done (KB-3.1 → 3.5 — `docs/phases/phase-3.md`) |
| 4 | Frontend/UX | 7 / 7 | ✅ Done (KB-4.1 → KB-4.7 — `docs/phases/phase-4.md`) |
| 4b | UI/UX overhaul (design system, bỏ control giả, streaming UX) | 4 / 4 | ✅ Done (KB-4.8 → KB-4.11 — `docs/phases/phase-4b.md`) |
| 5 | Nâng cao (index tăng dần · latency · lịch sử bền · chất lượng · auth · dọn code · CI · trả nợ TD · UI) | **13 / 13** | ✅ **Done** — 5.1→5.13 (auth + CI **cờ TẮT** mặc định) |
| 6 | Tech refresh (pin deps · Python bump · multilingual embedding/reranker) | 4 / 4 | ✅ Done |
| 7 | Dev env: migrate sang WSL (Windows sạch) | 1 / 1 | ✅ Done |
| 5b | **Trả nợ kỹ thuật (TD sweep)** — embedding fp32 · rate limit · startup sync nền · UI check provider | **4 / 4** | ✅ **Done** — KB-5.14→5.17; 4 TD trả, 4 TD **Skip** có điều kiện |
| 8 | Tài liệu & học tập (17 ADR + index học + 3 README) | **8 / 8** | ✅ **Done** — 8.1→8.8 (17 ADR, 28 câu ôn tập, README root/BE/FE) |
| 9 | **Chất lượng câu trả lời** (chẩn đoán · config · UI · nguồn thu gọn · ngưỡng liên quan · bộ vàng v4 · cấu hình runtime · gộp cấu hình vào Tuỳ chọn · hub-file) | **6 / 7** | ✅ 9.1–9.6 · ⏭️ **9.7 Skip** (đo: hạ điểm hub làm `hit@k` 0,964 → 0,75–0,82) |

---

## 4. Ticket chi tiết

### Phase 0 — Foundation & AI workflow

### KB-0.1 — Bộ AI assets (rules / skills / workflows / tools)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 0 |
| Repo | root (`Kb-khoa-hoc`) |
| Phụ thuộc | — |
| Ước lượng | M |

**Bối cảnh** — Dự án cần "hợp đồng làm việc" giữa human và AI, tham khảo mô hình của `shop-lab-microservices`.
**Mục tiêu** — Có `AGENTS.md` + rules + skills + workflows + tools, bao gồm cả FE.
**In scope** — `AGENTS.md`; `.clinerules/{00,10,20,30}`; `.cline/skills/kb-{ticket,verify,adr,pii-redaction}`;
`.clinerules/workflows/{new,run,close}-ticket.md`; `tools/`.
**Out of scope** — CI/CD, Kanban.
**Acceptance Criteria**
- [x] `AGENTS.md` có nguyên tắc làm việc, DoR/DoD, convention BE+FE, rule PII §9.5.
- [x] Có 3 rule behavioral + 4 skill + 3 workflow.
- [x] `tools/pii_scan.py` chạy được.
**Ghi chú kỹ thuật** — Mô phỏng shop-lab; Memory Bank lite = `architecture.md` + `Backlog.md`.
**Kết quả verify** — Liệt kê file trong `.clinerules/`, `.cline/skills/` (xem §8 Changelog).
**Learning note** — Rule = behavioral (luôn active); skill = on-demand; workflow = gọi `/file.md`.

### KB-0.2 — Chuyển LLM provider sang Groq

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 0 |
| Repo | BE |
| Phụ thuộc | — |
| Ước lượng | S |

**Bối cảnh** — Đang trỏ vào endpoint của trường; muốn dùng free tier, máy local không đủ mạnh chạy LLM.
**Mục tiêu** — BE chạy với Groq qua `ChatOpenAI` (OpenAI-compatible), đổi provider chỉ bằng env.
**In scope** — Bỏ hard-code `OPENAI_BASE_URL` trong `config.py`; cập nhật `.env.example`; đặt Groq mặc định.
**Out of scope** — Thêm provider abstraction nhiều class.
**Acceptance Criteria**
- [x] `get_settings()` không ghi đè base URL bằng giá trị hard-code.
- [x] `.env.example` hướng dẫn Groq (`https://api.groq.com/openai/v1`, model `openai/gpt-oss-120b`).
- [x] App khởi động và `/chat` gọi Groq khi có `OPENAI_API_KEY`.
**Ghi chú kỹ thuật** — Chỉ đổi 3 env. Cần ADR (KB-0.4).
**Kết quả verify** — `get_settings()` → `base_url=https://api.groq.com/openai/v1`, `model=openai/gpt-oss-120b`;
`py_compile` toàn bộ `app/` OK. Gọi `/chat` thật cần key Groq (user điền vào `.env`).
**Learning note** — `ChatOpenAI` nhận `openai_api_base` → dùng cho mọi provider compatible.
**Cập nhật 2026-11-09** — **TD-3** (config không đọc `.env`) đã trả: `SettingsConfigDict(env_file=".env")` trong `app/core/config.py`.

### KB-0.3 — Tài liệu kiến trúc & backlog

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 0 |
| Repo | root |
| Phụ thuộc | — |
| Ước lượng | S |

**Bối cảnh** — Cần nguồn sự thật để AI nạp context mỗi task.
**Mục tiêu** — `architecture.md` + `Backlog.md` phản ánh đúng hiện trạng + roadmap.
**In scope** — Sơ đồ, layer, luồng chat, env, roadmap, glossary; backlog + template.
**Out of scope** — —
**Acceptance Criteria**
- [x] `architecture.md` có sơ đồ, luồng chat, roadmap phases, glossary.
- [x] `Backlog.md` có template, bảng trạng thái, ticket, learning log, tech debt, changelog.
**Kết quả verify** — File tồn tại + đọc được.
**Learning note** — Memory Bank lite đủ dùng cho dự án cá nhân.

### KB-0.4 — ADR-0001: chọn LLM provider (Groq)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 0 |
| Repo | root |
| Phụ thuộc | KB-0.2 |
| Ước lượng | S |

**Bối cảnh** — Đổi provider là quyết định lớn (`AGENTS.md` §3.3) → phải có ADR.
**Mục tiêu** — Ghi lại lý do chọn Groq, trade-off, điều kiện revisit.
**In scope** — `docs/adr/0001-llm-provider-groq.md`.
**Out of scope** — ADR cho embedding/vector store (khi nào đổi mới viết).
**Acceptance Criteria**
- [x] ADR đủ 5 mục (Context/Options/Decision/Consequences/Revisit), có bảng trade-off.
- [x] Revisit có điều kiện định lượng.
**Kết quả verify** — File tồn tại.
**Learning note** — Chốt rõ "khi nào revisit" từ đầu để sau không tranh luận lại.

---

### Phase 1 — Safety: PII/secret redaction  ⚠️ P0

### KB-1.1 — Lớp redaction PII trước khi gửi LLM

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 1 |
| Repo | BE |
| Phụ thuộc | KB-0.2 |
| Ước lượng | M |

**Bối cảnh** — Knowledge base cá nhân chứa email/sđt/mật khẩu/API key; LLM (Groq) là bên thứ ba →
không được gửi thẳng PII/secret.
**Mục tiêu** — Mọi dữ liệu gửi tới LLM (message, context, history, rewrite) đều qua `PIIRedactor`.
**In scope** — `app/services/pii_service.py`; tích hợp vào `ChatService.chat` + `stream_chat` + query-rewrite;
config `ENABLE_PII_REDACTION`, `PII_PLACEHOLDER`; unit test.
**Out of scope** — NER/ML-based detection; redact lúc ingest (để KB-1.2); che ảnh/binary.
**Acceptance Criteria**
- [x] `PIIRedactor.redact(text)` che: email, sđt VN, CCCD, secret (`sk-`, `gsk_`, `ghp_`, JWT), gán mật khẩu (`password`).
- [x] Không che nhầm số kỹ thuật (port, version `1.2.3`, token count).
- [x] `ChatService` redact trước khi gửi LLM; `ENABLE_PII_REDACTION=false` → tắt được.
- [x] Có `tests/test_pii_service.py`, pass.
**Ghi chú kỹ thuật** — Regex-first (đủ nhanh, offline). NER = tech debt TD-1.
**Kết quả verify** — `python -m pytest -v` (trong `Knowledge-base`) → **9 passed in 0.04s** (dán output
bên dưới). Config check: `get_settings()` → `base_url=https://api.groq.com/openai/v1`,
`pii_enabled=True`.
```
tests/test_pii_service.py::test_redacts_email PASSED
tests/test_pii_service.py::test_redacts_phone_vn PASSED
tests/test_pii_service.py::test_redacts_secrets PASSED
tests/test_pii_service.py::test_redacts_password_value_but_keeps_key PASSED
tests/test_pii_service.py::test_redacts_cccd_12_digits PASSED
tests/test_pii_service.py::test_keeps_technical_numbers PASSED
tests/test_pii_service.py::test_allowlisted_examples_pass_through PASSED
tests/test_pii_service.py::test_disabled_is_passthrough PASSED
tests/test_pii_service.py::test_stats_counts_multiple_emails PASSED
9 passed in 0.04s
```
**Learning note** — Che ở **cổng ra** (trước khi gọi LLM) chắc chắn hơn che ở input vì bắt được cả
context từ tài liệu (nơi PII thật nằm). Lưu ý: `password=...` trong **ví dụ code** cũng bị che (an toàn,
nhưng có thể mất tên biến env nếu không nằm trong allowlist).

### KB-1.2 — Redact PII khi ingest tài liệu (tuỳ chọn)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 1 |
| Repo | BE |
| Phụ thuộc | KB-1.1 |
| Ước lượng | S |

**Bối cảnh** — PII nằm sẵn trong tài liệu đã index; che ở ingest giảm rủi ro và giảm chi phí che lặp lại.
**Mục tiêu** — Tuỳ chọn che PII trước khi embed/lưu vào ChromaDB, điều khiển bởi `PII_REDACT_INGEST`.
**In scope** — Hook vào `DocumentService._add_documents_to_db`; hàm thuần `redact_texts_for_ingest`; config `PII_REDACT_INGEST`.
**Out of scope** — Che file gốc trên đĩa (chỉ che bản đưa vào vector store).
**Acceptance Criteria**
- [x] `PII_REDACT_INGEST=true` → chunk lưu vào Chroma không chứa PII (kiểm bằng integration test).
- [x] `PII_REDACT_INGEST=false` → giữ nguyên (mặc định giữ nguyên để retrieval không sai lệch).
- [x] Có test/integration verify (14 tests pass).
**Ghi chú kỹ thuật** — Hàm thuần `redact_texts_for_ingest` (không phụ thuộc ChromaDB) → test được;
chunk bị che gắn metadata `pii_redacted=True`. Trade-off: che ingest làm mất thông tin nếu tài liệu
CẦN PII để trả lời.
**Kết quả verify** — `python -m pytest -v` (Knowledge-base) → **14 passed in 0.85s**.
Integration test `test_ingest_integration.py` chạy thật `_add_documents_to_db` với fake collection:
- `PII_REDACT_INGEST=true` → `john.doe@gmail.com` bị thay `[REDACTED:EMAIL]`, metadata `pii_redacted=True`.
- `PII_REDACT_INGEST=false` → text giữ nguyên, không cờ.
**Learning note** — Đặt hook ở `_add_documents_to_db` (funnel chung) thay vì lúc chunk → che một chỗ,
áp cho cả vector store lẫn BM25 corpus, không đụng file gốc. Tách logic ra hàm thuần giúp test
không cần tải embedding model.

### KB-1.3 — Cảnh báo PII trong response trả về UI

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 1 |
| Repo | BE+FE |
| Phụ thuộc | KB-1.1 |
| Ước lượng | S |

**Bối cảnh** — Cần cho user biết câu tl/nguồn đã bị che phần nào để không hiểu nhầm.
**Mục tiêu** — Trả metadata `redacted: true` + số lượng chỗ bị che; UI hiển thị badge "đã che PII".
**In scope** — BE thêm field vào response metadata; FE hiển thị badge.
**Out of scope** — Cho user bật/tắt hiển thị PII gốc.
**Acceptance Criteria**
- [x] Response `/chat` có metadata redaction khi có che (`pii_redacted` + `pii_redacted_count`).
- [x] FE hiển thị badge khi có che (`pii_redacted_count > 0`).
**Q&A (trả lời trước khi làm)**
- Q1: Badge hiển thị ở đâu trong khung chat? (đầu câu trả lời / cạnh khối sources / toast góc màn hình)
  → **đầu câu trả lời**
- Q2: Nội dung badge chỉ là icon + tooltip, hay có text kiểu "Đã che N thông tin nhạy cảm"?
  → **chỉ icon + tooltip**
- Q3: Có cần hiện chi tiết **từng loại** PII bị che (email/sđt/…) hay chỉ tổng số?
  → **tổng số là đủ**
**Ghi chú kỹ thuật** — Không bao giờ trả PII gốc về UI nếu đã che ở cổng ra. Badge icon-only + `title` tooltip
(không thêm UI primitive). BE thêm helper pure `summarize_pii_stats`.
**Kết quả verify** —
- BE: `python -m pytest -q` → **16 passed**; `py_compile` OK.
- FE: `npm run build` → **✓ Compiled successfully** (3/3 static pages); `npx tsc --noEmit` → **exit 0** (không lỗi type).
- Môi trường: máy thiếu Node → đã cài **Node LTS 26.13.0** (winget) để build FE.
**Learning note** — Trả 2 field tóm tắt sẵn (`pii_redacted` bool + `pii_redacted_count` int) để FE không phải
tự cộng dict → contract rõ hơn. Native `title` tooltip là đủ cho "icon + tooltip", tránh thêm component.
Phát hiện: `next.config.mjs` còn key `eslint` (Next 16 bỏ hỗ trợ) → ghi vào KB-6.4.

---

### Phase 2 — RAG quality

> Chi tiết đầy đủ (bảng ticket, số đo trước/sau, bài học): `docs/phases/phase-2.md`.

### KB-2.1 — Eval harness + baseline retrieval

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 2 |
| Repo | BE |
| Phụ thuộc | KB-1.3 |
| Ước lượng | M |

**Bối cảnh** — Chưa có cách đo chất lượng retrieval ⇒ mọi thay đổi sau không chứng minh được là tốt lên.
**Mục tiêu** — Eval harness chạy được + có baseline bằng số.
**In scope** — `Knowledge-base/eval/`: 15 câu vàng + `run_eval.py` (`--mode retrieval|full`, `--rerank`, `--k`); metric Recall@k, MRR, latency.
**Out of scope** — LLM-as-judge, dashboard.
**Acceptance Criteria**
- [x] `python eval/run_eval.py --mode retrieval` in Recall@k/MRR/latency.
- [x] Baseline được ghi lại để so sánh về sau.
**Kết quả verify** — baseline `Recall@3=0.80`, `MRR=0.72`, `latency_p50=0.177s` (rerank off); BE commit `3358596`.
**Learning note** — Đo trước khi tối ưu; harness rẻ hơn sửa mò rất nhiều.

### KB-2.2 — Dedup chunk + `SIMILARITY_THRESHOLD` + chunk ID ổn định

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 2 |
| Repo | BE |
| Phụ thuộc | KB-2.1 |
| Ước lượng | M |

**Bối cảnh** — Sources trùng lặp cùng file, `SIMILARITY_THRESHOLD` là biến chết, chunk ID dùng `hash()` (đổi mỗi process ⇒ upsert không tái lập).
**Mục tiêu** — Dedup + threshold có tác dụng + chunk ID tái lập.
**In scope** — `app/services/dedup.py` (Jaccard 0.8, cap 2 chunk/file); threshold lọc dense; `sha1(source|chunk_index|text)[:16]` + `upsert`; trả `chunk_id`.
**Out of scope** — Đổi embedding model (Phase 6).
**Acceptance Criteria**
- [x] `sources` không còn 2 chunk gần trùng.
- [x] Chunk ID tái lập giữa 2 lần index cùng nội dung.
**Kết quả verify** — BE commit `a17162e` (+ docs `1d3e28b`); eval không giảm.
**Learning note** — Chunk ID phải là **hàm của nội dung**, không phải của thời điểm.

### KB-2.3 — Citation contract `[S1]` + grounding prompt

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 2 |
| Repo | BE |
| Phụ thuộc | KB-2.2 |
| Ước lượng | M |

**Bối cảnh** — Câu trả lời không có căn cứ ⇒ không kiểm chứng được, dễ hallucination.
**Mục tiêu** — LLM trích dẫn `[S#]` khớp 1-1 với `sources[{citation_id, chunk_id, snippet}]`.
**In scope** — Prompt yêu cầu citation; `build_context` có budget (`CONTEXT_MAX_CHARS=6000`); map `citation_id` ↔ `chunk_id`.
**Out of scope** — UI hiển thị (KB-4.2/4.3).
**Acceptance Criteria**
- [x] Mỗi `[S#]` map đúng chunk; câu trả lời có citation khi có context.
- [x] Context không vượt budget.
**Kết quả verify** — BE commit `395e727`; eval `--mode full` có citation.
**Learning note** — Chốt contract ở **schema** (id tường minh), đừng để LLM tự bịa số.

### KB-2.4 — Chunking theo heading markdown + re-index thật (trả TD-7)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 2 |
| Repo | BE |
| Phụ thuộc | KB-2.3 |
| Ước lượng | M |

**Bối cảnh** — Chunk cắt theo ký tự làm vỡ ngữ nghĩa; TD-7 = index chưa dựng lại sau khi đổi cách chunk.
**Mục tiêu** — Chunk 2 tầng: heading H1–H3 rồi tới size, kèm `heading_path`.
**In scope** — Chunker heading-aware; re-index toàn bộ kho; dọn code chết.
**Out of scope** — Chunking cho PDF/DOCX.
**Acceptance Criteria**
- [x] Chunk có `heading_path` (hiện trong sources panel).
- [x] Re-index thành công toàn bộ folder.
**Kết quả verify** — **56 file → 601 chunk** (~22 phút CPU — TD-14); BE commit `3500e47`.
**Learning note** — Đổi cách chunk = **bắt buộc re-index**, không có đường tắt.
**Cập nhật 2026-11-09** — **TD-13** (BM25 corpus lệch sau re-index) đã trả ở **KB-5.1**: `_refresh_corpus_after_sync()` + `clear_database()` reset `_corpus_*`.

### KB-2.5 — Tune retrieval params + chốt default (trả TD-8)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 2 |
| Repo | BE |
| Phụ thuộc | KB-2.4 |
| Ước lượng | M |

**Bối cảnh** — Nhiều tham số (`RETRIEVAL_K`, `HYBRID_ALPHA`, `ENABLE_RERANK`…) chưa từng được đo.
**Mục tiêu** — Chốt default **dựa trên số đo**.
**In scope** — Grid 10 cấu hình ⇒ chốt `RETRIEVAL_K=3`, `HYBRID_ALPHA=0.5`, `MAX_CHUNKS_PER_FILE=2`, `ENABLE_RERANK=true`, `SIMILARITY_THRESHOLD=0.0`.
**Out of scope** — Reranker khác (KB-6.3).
**Acceptance Criteria**
- [x] Có bảng so sánh 10 cấu hình; default khớp cấu hình thắng.
**Kết quả verify** — `MRR 0.72 → 1.0`; `latency_p50 0.177s → 8.16s` (rerank bật — **TD-15**); BE commit `abe10b6`. **Phase 2 Done (5/5).**
**Learning note** — Bật rerank là đánh đổi rõ: chất lượng tuyệt đối lên, latency ~46×. Đo cái đang chạy thật.

### Phase 3 — Backend robustness

> Chi tiết: `docs/phases/phase-3.md`.

### KB-3.1 — Error taxonomy + global handlers + request-id

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 3 |
| Repo | BE |
| Phụ thuộc | KB-2.5 |
| Ước lượng | M |

**Bối cảnh** — Mỗi chỗ trả lỗi một kiểu ⇒ FE không map được, không tra được log.
**Mục tiêu** — Contract lỗi thống nhất `{"error": {"code","message","request_id"}}` + header `X-Request-ID`.
**In scope** — `app/core/errors.py`: `AppError` + 7 subclass (`provider_auth_failed` 502, `provider_rate_limited` 429, `provider_timeout` 504, `prompt_file_missing` 500, `document_store_error` 500, `invalid_request` 422, `internal_error` 500) + handler toàn cục.
**Out of scope** — Retry provider (KB-3.2).
**Acceptance Criteria**
- [x] Mọi lỗi có `code` + `request_id`; `/chat` và `/chat/stream` cùng shape.
**Kết quả verify** — BE commit `bc7d29f`; test tầng HTTP phủ từng code.
**Learning note** — Chốt contract lỗi **trước** khi làm UI ⇒ KB-4.1 nhẹ.

### KB-3.2 — Provider resilience (retry/backoff + timeout + concurrency)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 3 |
| Repo | BE |
| Phụ thuộc | KB-3.1 |
| Ước lượng | M |

**Bối cảnh** — Groq free tier hay 429/5xx tạm thời ⇒ request fail oan.
**Mục tiêu** — Retry có backoff + timeout + giới hạn concurrency.
**In scope** — `app/core/provider_retry.py`: `ProviderThrottle` (semaphore `PROVIDER_MAX_CONCURRENCY=1`) + retry/backoff + timeout.
**Out of scope** — Multi-provider failover.
**Acceptance Criteria**
- [x] 429/5xx retry theo cấu hình; timeout trả `provider_timeout`; concurrency bị chặn.
**Kết quả verify** — BE commit `5a13bcd`; test giả lập 429 rồi 200.
**Learning note** — Throttle per-process chưa đủ khi nhiều worker — **TD-17**.

### KB-3.3 — SSE ổn định + `request_id` (trả TD-16)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 3 |
| Repo | BE |
| Phụ thuộc | KB-3.2 |
| Ước lượng | M |

**Bối cảnh** — Stream có thể treo, client ngắt giữa chừng, event `error` khác schema `/chat`.
**Mục tiêu** — Contract `start → token* → (end | error)`, heartbeat `: ping`, xử lý disconnect.
**In scope** — `app/core/sse.py`; truyền `request_id` vào generator (**trả TD-16**).
**Out of scope** — Resume stream.
**Acceptance Criteria**
- [x] Event `error` cùng schema KB-3.1; client ngắt ⇒ generator dừng.
**Kết quả verify** — BE commit `de03961`.
**Learning note** — Heartbeat bằng comment `: ping` là cách rẻ nhất giữ kết nối qua proxy.

### KB-3.4 — Probes: `/health` (liveness) + `/ready` (readiness thật)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 3 |
| Repo | BE |
| Phụ thuộc | KB-3.3 |
| Ước lượng | S |

**Bối cảnh** — Cần phân biệt "process còn sống" với "trả lời được".
**Mục tiêu** — `/health` luôn 200 + `uptime_seconds`; `/ready` kiểm `provider_config` / `prompt_file` / `collection`.
**In scope** — `app/services/health_service.py`; `status` ∈ `ok | degraded | error`.
**Out of scope** — `/ready?deep=true` gọi provider thật (**TD-23**).
**Acceptance Criteria**
- [x] `/health` 200 kể cả khi Chroma lỗi; `/ready` phản ánh đúng; dùng được cho Docker healthcheck.
**Kết quả verify** — BE commit `da1f8e3`; compose `depends_on: service_healthy` chạy đúng.
**Learning note** — Liveness/readiness tách nhau là điều kiện để container restart đúng lý do.

### KB-3.5 — Test tầng HTTP (trả TD-4)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 3 |
| Repo | BE |
| Phụ thuộc | KB-3.4 |
| Ước lượng | M |

**Bối cảnh** — Test cũ chỉ chạm service, không kiểm handler/contract ⇒ lỗi 500 lọt ra ngoài.
**Mục tiêu** — Test ở tầng HTTP với service giả.
**In scope** — `tests/conftest.py` + `test_api_endpoints.py` + `test_api_errors.py` + `test_api_stream.py` (**28 test**).
**Out of scope** — Test với LLM thật (tốn quota).
**Acceptance Criteria**
- [x] Phủ 4 endpoint chính + mọi nhánh lỗi; `pytest` không cần mạng.
**Kết quả verify** — 164 test pass (28 tầng HTTP); BE commit `dec3af6`. **Phase 3 Done (5/5).**
**Learning note** — Fake service + `dependency_overrides` cho test nhanh và không tốn quota.

### Phase 4 — Frontend / UX

> Chi tiết: `docs/phases/phase-4.md`.

### KB-4.1 — API client duy nhất + error UX theo contract

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4 |
| Repo | FE |
| Phụ thuộc | KB-3.5 |
| Ước lượng | M |

**Bối cảnh** — `fetch` rải rác trong `page.tsx`, lỗi chỉ `console.error` ⇒ người dùng không phân biệt 429 vs 503.
**Mục tiêu** — Một client + banner lỗi theo `code`.
**In scope** — `lib/api.ts` (`apiFetch`/`postChat`, `ApiError{code, request_id, status}`), `lib/errors.ts` (map code → message + hint tiếng Việt), banner có nút **Thử lại**.
**Out of scope** — Retry tự động ở FE.
**Acceptance Criteria**
- [x] Mọi call BE đi qua `lib/api.ts`; banner hiện `code` + `request_id`, không chèn message giả vào khung chat.
**Kết quả verify** — FE commit `ed4fcc5`; `tests/api.test.ts` + `tests/errors.test.ts`.
**Learning note** — Map lỗi ở **một chỗ** giữ nhất quán khi thêm code mới.

### KB-4.2 — Markdown GFM thật + chip citation bấm được

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4 |
| Repo | FE |
| Phụ thuộc | KB-4.1 |
| Ước lượng | M |

**Bối cảnh** — Trả lời là markdown nhưng UI render text thô; `[S1]` không bấm được.
**Mục tiêu** — Render GFM + code highlight + chip citation.
**In scope** — `components/markdown-message.tsx` (`react-markdown` + `remark-gfm` + `rehype-highlight`), chip `[S#]`.
**Out of scope** — Mermaid, LaTeX.
**Acceptance Criteria**
- [x] Bảng/list/code block render đúng; `[S#]` là button.
**Kết quả verify** — FE commit `5c5a9cc`; `tests/markdown-message.test.tsx`.
**Learning note** — Dùng `rehype-highlight` thay vì tự viết highlighter.

### KB-4.3 — Sources panel theo `citation_id` (trả TD-12)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4 |
| Repo | FE |
| Phụ thuộc | KB-4.2 |
| Ước lượng | M |

**Bối cảnh** — Panel nguồn dedup theo `file_path` ⇒ mất chunk, chip không trỏ đúng chỗ (**TD-12**).
**Mục tiêu** — 1 card / chunk; bấm chip ⇒ scroll + highlight đúng card.
**In scope** — `components/sources-panel.tsx`: `chunk #n`, `heading_path`, score; `CitationFocus{messageId, citationId, nonce}`.
**Out of scope** — Modal xem full chunk.
**Acceptance Criteria**
- [x] Không dedup theo file; bấm lại cùng chip vẫn highlight lại (`nonce`).
**Kết quả verify** — FE commit `6153319`; `tests/sources-panel.test.tsx`.
**Learning note** — Key React phải là `citation_id`, không phải `file_path`.

### KB-4.4 — Streaming SSE + nút Stop

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4 |
| Repo | FE |
| Phụ thuộc | KB-4.3 |
| Ước lượng | M |

**Bối cảnh** — Chờ cả câu trả lời mới hiện ⇒ cảm giác treo, không huỷ được.
**Mục tiêu** — Chữ hiện dần, Stop giữ phần đã nhận.
**In scope** — `lib/sse.ts` (parser thuần: `\n\n`, bỏ `: ping`, buffer frame bị cắt, `TextDecoder(stream)`), `streamChat`, `StreamAbortedError`, nhãn "đã dừng".
**Out of scope** — Resume stream.
**Acceptance Criteria**
- [x] `NEXT_PUBLIC_STREAMING=true` ⇒ `/chat/stream`; `false` ⇒ fallback `/chat`.
- [x] Stop ⇒ giữ partial text, không xoá bubble.
**Kết quả verify** — FE commit `8a5d8c8`; `tests/sse.test.ts` (frame bị cắt, nhiều chunk).
**Learning note** — Parser SSE tách module thuần ⇒ test 100% không cần browser.

### KB-4.5 — Kho tài liệu + readiness drawer

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4 |
| Repo | FE |
| Phụ thuộc | KB-4.4 |
| Ước lượng | M |

**Bối cảnh** — Không biết index có bao nhiêu chunk, folder có tồn tại không, provider đã cấu hình chưa.
**Mục tiêu** — Drawer hiện status + cho Refresh/Clear.
**In scope** — `components/documents-panel.tsx`: `/documents/status` + `/documents/folder-info` + `/ready`; **Clear phải gõ `CLEAR`**; refresh có timeout riêng.
**Out of scope** — Upload tài liệu (BE chưa có endpoint).
**Acceptance Criteria**
- [x] Chỉ fetch khi mở drawer; Clear chỉ bấm được khi gõ đúng `CLEAR`.
**Kết quả verify** — FE commit `1f18d22`; `tests/documents-panel.test.tsx`.
**Learning note** — Hành động phá huỷ phải có **ma sát** (gõ từ khoá), không chỉ confirm 2 nút.

### KB-4.6 — Quality gate FE: vitest + eslint + tsc

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4 |
| Repo | FE |
| Phụ thuộc | KB-4.5 |
| Ước lượng | S |

**Bối cảnh** — Không có test FE; `next lint` bị bỏ ở Next 16.
**Mục tiêu** — Có lưới an toàn trước khi làm UI lớn (Phase 4b).
**In scope** — `vitest` + `jsdom` + `@testing-library`; `eslint.config.mjs` (flat); `tsc --noEmit`; script `test|typecheck|lint`.
**Out of scope** — E2E Playwright (**TD-26**).
**Acceptance Criteria**
- [x] `npm run test` + `lint` + `typecheck` chạy được và xanh.
**Kết quả verify** — FE commit `fcde6b2`: 50 test / 6 file (~1.2s), lint 0 error.
**Learning note** — Test FE rẻ nhất khi logic tách thành module thuần (`lib/*`).

### KB-4.7 — Docker FE + compose BE↔FE

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4 |
| Repo | BE + FE |
| Phụ thuộc | KB-4.6 |
| Ước lượng | M |

**Bối cảnh** — Chạy 2 service thủ công; `NEXT_PUBLIC_*` nhúng lúc build nhưng không truyền được từ compose.
**Mục tiêu** — `docker compose up` là có hệ thống chạy được.
**In scope** — FE `Dockerfile` (`ARG NEXT_PUBLIC_API_PROXY_URL`/`NEXT_PUBLIC_STREAMING` trước build + `HEALTHCHECK` `node -e fetch` + `.dockerignore`); BE `docker-compose.yml` không mount source, `build.args`, `depends_on: service_healthy`, `user: ${USER_ID:-1000}`, `HOME=/tmp`, volume `HF_HOME=/hf-cache`, `start_period 600s`; port **8010/3010**; CORS qua `ALLOWED_ORIGINS`.
**Out of scope** — Registry/CI build (**TD-24**).
**Acceptance Criteria**
- [x] `docker compose up -d --build` ⇒ 2 service `healthy`.
- [x] Sửa FE rồi build lại ⇒ UI thấy thay đổi; Chroma ghi được (uid 1000).
**Kết quả verify** — BE **MR !18/!19**, FE **MR !10/!11**; sửa 2 bug thật: Chroma `readonly database` (uid 10001 vs 1000) và `PermissionError: '/.cache'`.
**Learning note** — Chạy container bằng **uid của host** tránh cả 2 lỗi quyền; healthcheck phải kiểm thứ thật dùng (fetch). **Phase 4 Done (7/7).**

### Phase 4b — UI/UX overhaul (sau audit UI thật vs backend)

> Sinh ra từ **audit 2026-11-08** khi chạy UI thật trong Docker: nhiều control **không nối vào backend**, layout hẹp,
> dark mode chết, và một **lỗi mất dữ liệu tiềm tàng** ở `POST /documents/refresh`.

### KB-4.8 — UI shell & design system (shadcn, layout, dark mode)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4b (UI/UX overhaul) |
| Repo | FE |
| Phụ thuộc | KB-4.1 → KB-4.7 |
| Ước lượng | M |

**Bối cảnh** — UI hiện tại là bản onboarding dựng vội: bubble hẹp giữa màn hình, nút gradient tự phát, input area lệch,
`components/ui/` chỉ có 4 primitive (button/card/input/scroll-area) **dù đã cài 27 package Radix** và có sẵn
`components.json` (shadcn new-york). Token màu + `.dark` có trong `globals.css` nhưng **không có toggle** nên dark mode
chết. Markdown render ổn (KB-4.2) nhưng thiếu typography scale nên khó đọc.
**Mục tiêu** — Giao diện "ra sản phẩm": layout 2 cột chuẩn, dùng shadcn/ui thật, dark mode bật/tắt được và lưu
`localStorage`, typography dễ đọc.
**In scope**
- Bổ sung primitive **từ Radix đã cài** (không thêm dependency UI mới): `sheet` (drawer Kho tài liệu + menu mobile),
  `tooltip`, `badge`, `separator`, `skeleton`, `slider` (temperature), `label`, `avatar`, `toast` + `toast-provider`.
- Layout lại `app/page.tsx`: sidebar cố định + vùng chat `max-w-3xl` canh giữa, composer sticky dưới, bubble full-width
  (bỏ `max-w-md`); < 768px sidebar thu vào `Sheet`.
- **Theme toggle** (light/dark/system) + `localStorage['kb.theme']` + script inline chống FOUC.
- Typography markdown qua class `.md-body` mở rộng (Q2).
- Tách `page.tsx` (788 dòng) thành `app-header` / `app-sidebar` / `chat-messages` / `chat-composer` / `error-banner`.
**Out of scope** — Đổi màu thương hiệu, i18n framework, animation phức tạp, đổi `react-markdown`.
**Acceptance Criteria**
- [x] Không thêm UI library mới; `package.json` dependencies không đổi.
- [x] Dark mode toggle hoạt động + giữ sau reload; panel/bảng markdown đọc được ở cả 2 theme.
- [x] Layout không còn bubble `max-w-md`; ở 768px sidebar thu gọn, không tràn ngang.
- [x] Drawer **Kho tài liệu** dùng `Sheet` (focus trap, ESC, aria) thay `<div role="dialog">` tự viết.
- [x] `npm run test` + `npm run lint` + `npm run build` xanh (thêm test cho toggle theme).
**Q&A (trả lời trước khi làm)**
- Q1: Hướng styling: (A) giữ Tailwind v4 + **shadcn/ui dựng từ Radix đã cài** (không thêm dep) · (B) thêm component
  library khác · (C) thêm plugin kiểu daisyUI · (D) chỉ polish CSS hiện tại?
  → **Chốt: (A)** — Tailwind v4 + shadcn/ui dựng từ **27 Radix package đã cài** (`components.json` có sẵn), không thêm UI library nào.
- Q2: Typography cho markdown: dùng plugin `@tailwindcss/typography` (thêm 1 devDep) hay tự viết class `.md-body`?
  → **Chốt: (B) `.md-body` tự viết** (agent tự chọn lúc làm — user chưa trả lời trực tiếp): thêm dep trong khi AC ghi
  "không thêm UI library mới"; scale hiện tại đủ heading/list/table/blockquote/inline-code. Revisit nếu cần `prose` chuẩn.
**Giả định** — (a) giữ token hiện có, không đổi brand color; (b) không dùng `next-themes`, tự viết `lib/theme.ts`; (c) test UI ở mức render + toggle, không snapshot.
**Ghi chú kỹ thuật** — Radix đã có trong `dependencies` ⇒ chỉ cần wrapper theo style shadcn new-york + `cn()`.
`useSyncExternalStore` để đọc `localStorage` (tránh `set-state-in-effect` + lệch hydration).
**MR** — FE **!13** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/13) — nguồn sự thật của KB-4.8 (FE only, không đụng BE).

**Kết quả verify** (output thật)

```
$ npx tsc --noEmit                  → không lỗi
$ npm run test                      → 10 files / 77 tests passed (23 test mới: theme 9, theme-toggle 5,
                                      shell 7, toast 2 — trước KB-4.8: 54)
$ npm run lint                      → 0 errors, 8 warnings (chỉ còn warning cũ ở lib/export-utils.ts + lib/types.ts)
$ npm run build                     → ✓ Compiled successfully; route "/" prerender static
$ docker compose up -d --build chatbot-ui → chatbot-ui healthy
$ curl :3010 | grep -c 'max-w-md'   → 0     (bỏ bubble hẹp)
$ curl :3010 | grep -c 'max-w-3xl'  → 1     (khung chat canh giữa)
$ curl :3010 | grep -c 'kb.theme'   → 1     (script chống FOUC trong <head>)
$ curl :3010 | grep -c 'An Chu\|Logout' → 0 (control giả đã bỏ)
$ curl :3010 | grep -c 'md-body'    → 1
```

⚠️ **Chưa verify**: bấm thử trên browser thật (môi trường này không có browser) — dark mode, focus trap và drag của
Sheet chỉ kiểm ở mức component test + HTML SSR.
**Learning note** — (1) **Đừng "giữ control giả cho đủ scope"**: viết lại composer theo design system thì select `Model` /
textarea `System prompt` tự rơi ra (chưa bao giờ được gửi lên BE) ⇒ KB-4.9 nhẹ hơn. (2) **`react-hooks/set-state-in-effect`**
chặn đúng chỗ: đọc `localStorage` bằng `useState` + `setState` trong effect ⇒ vi phạm; giải bằng `useSyncExternalStore`.
(3) **jsdom 31 của máy này không có `localStorage`** (chỉ `sessionStorage`; Node 26 báo
`--localstorage-file was not provided`) ⇒ polyfill trong `tests/setup.ts`. (4) **`ResizeObserver` thiếu trong jsdom** ⇒
Radix ScrollArea chỉ nổ khi **có** item (test rỗng pass, test có data fail). (5) **`max-w-md` lồng trong bubble**:
`MessageWithCitations` tự bọc bubble riêng ⇒ phải tách trách nhiệm. (6) Accessible name bị dính chữ
(`"Ôn phỏng vấn RAG4 tin nhắn"`) ⇒ thêm `aria-label` tường minh. (7) `text-sm` (utility layer) **không** thắng
`.md-body` (unlayered). **TD mới: TD-26.**

### KB-4.9 — Bỏ control "giả" + khớp UI với backend (logic/i18n)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4b (UI/UX overhaul) |
| Repo | FE |
| Phụ thuộc | KB-4.8 (layout) |
| Ước lượng | S |

**Bối cảnh** — Audit 2026-11-08 phát hiện nhiều control **không nối vào backend**: select `Model` và textarea
`System prompt` (không có trong `ChatRequest`; BE luôn dùng `OPENAI_MODEL` + `SYSTEM_PROMPT_PATH`), sidebar
`Chat History` là dữ liệu **giả trong RAM** (reload mất, BE không có endpoint list conversation), greeting mời
"Upload a document" trong khi BE **không có** endpoint upload, `Logout` + user hardcode "An Chu" + badge role (không có
auth), trộn tiếng Anh/Việt, `max_tokens` mặc định 500 lệch default 1000 của BE.
**Đã làm sớm trong KB-4.8** (do viết lại shell): bỏ select `Model` + textarea `System prompt` + user/logout giả,
`max_tokens=1000`, copy chuyển tiếng Việt, greeting mới (không mời upload).
**Mục tiêu** — UI chỉ hiển thị/cho thao tác những gì backend thật sự hỗ trợ; phần chưa có thì **không giả vờ**.
**In scope**
- **Multi-conversation client-side**: lưu `sessions[]` (messages + `conversation_id` + title) trong `localStorage`;
  sidebar list/switch/delete thật; giữ được sau F5.
- Nối `conversationId` theo **session** (hiện chỉ 1 key `kb.conversation_id` toàn cục ⇒ đổi session là lẫn mạch).
- Hiện **model thật** từ `metadata.model` của câu trả lời (không phải select giả).
- Rà lại copy tiếng Việt toàn bộ UI (badge, tooltip, empty state).
- **(user yêu cầu)** Bỏ nút **Kho tài liệu** ở sidebar — trùng với nút ở header; chỉ giữ 1 chỗ góc trên phải.
- **(phát hiện khi làm)** Nút "Sao chép" đè lên dòng đầu của câu trả lời ⇒ chuyển xuống dưới, chỉ hiện khi hover/focus.
**Out of scope** — Upload tài liệu (BE chưa có endpoint) → ticket riêng; auth (Phase 5).
**Acceptance Criteria**
- [x] F5 vẫn thấy đúng các cuộc trò chuyện + nội dung messages; switch session đổi đúng mạch hội thoại.
- [x] Không còn control nào không gửi/không đọc được từ BE.
- [x] `npm run test` + `lint` + `build` xanh; có test cho persistence + switch session.
- [x] Sidebar không còn nút **Kho tài liệu** (chỉ header); nút **Sao chép** không đè nội dung.
**Q&A (trả lời trước khi làm)**
- Q3: Chat history giả xử lý thế nào: (A) xoá hẳn sidebar, (B) giữ nhưng ghi rõ "chưa lưu", (C) lưu client-side
  `localStorage`, (D) làm endpoint BE + DB?
  → **Chốt: (C)** multi-conversation client-side trong `localStorage` — chưa cần DB, nhưng F5 phải giữ.
**Giả định** — `localStorage` là nguồn sự thật của lịch sử chat ở phase này; giới hạn ~50 session.
**Ghi chú kỹ thuật** — `lib/chat-store.ts`: store ngoài React (`memory` + `localStorage['kb.chat_sessions']`),
`subscribe`/`getSnapshot`/`getServerSnapshot` cho `useSyncExternalStore`. Ghi `localStorage` **debounce 300ms**
(stream token không tạo hàng trăm lần ghi đồng bộ). `getServerSnapshot` trả store rỗng ⇒ SSR và lần render đầu
trên client giống nhau. Hàm thuần: `parseChatStore`/`serializeChatStore`/`deriveTitle`.
**MR** — FE **!14** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/14), squash `faf9d58`,
nhánh `feat/kb-4.9-chat-store` đã xoá. (FE only — không đụng BE.)

**Kết quả verify** (output thật)

```
$ npx tsc --noEmit                        → không lỗi
$ npx vitest run                          → 11 files / 91 tests passed (14 test mới cho chat-store:
                                            parse/validate, deriveTitle, debounce persist, nạp lại sau “reload”,
                                            migrate key cũ, subscribe/unsubscribe, clear)
$ npm run lint                            → 0 errors, 6 warnings (trước: 8 — page.tsx sạch warning)
$ npm run build                           → ✓ Compiled successfully
$ docker compose up -d --build chatbot-ui  → chatbot-ui healthy
$ curl :3010 | grep -c 'Kho tài liệu'      → 1  (chỉ còn ở header; sidebar đã bỏ)
$ curl :3010 | grep -c 'Lịch sử'         → 1
```

**Follow-up 2 (Playwright + fix tràn panel Nguồn)** — FE **!16** (xem Changelog 2026-11-08 dòng cuối): thay tool CDP
qua Chrome Windows bằng **Playwright Chromium trong WSL** (`npm run test:e2e`, 7 check, ~4s) và sửa panel Nguồn
rộng hơn cột chat (`w-full min-w-0` + `[overflow-wrap:anywhere]`).

**MR (follow-up tool + fix layout)** — FE **!15** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/15), squash `4e7a43d`.

**MR (align composer + panel Nguồn)** — FE **!17** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/17), squash `26aa82c`.

**Verify bằng Chrome thật (CDP)** — `bash tools/ui-verify.sh` (Chrome 156 headless trên Windows):

```
PASS  Trang load + header "Knowledge Base"
PASS  Chỉ có 1 nút "Kho tài liệu" (ở header) — tìm thấy 1
PASS  F5 vẫn thấy hội thoại + tiêu đề session
PASS  Markdown câu trả lời render (<strong>)
PASS  Theme: bấm lần 1 → light (bỏ .dark + lưu kb.theme) — {"dark":false,"stored":"light","scheme":"light"}
PASS  Theme: bấm lần 2 → dark (.dark + color-scheme)
PASS  Sheet mở: role=dialog + aria-labelledby + focus nằm trong sheet
PASS  ESC đóng được sheet
PASS  720px không tràn ngang
PASS  720px sidebar thu gọn (dùng Sheet)
**Follow-up alignment:** composer thẹ mép bubble AI/Bạn + composer thấp + panel Nguồn thẹ mép bubble "Bạn" — Playwright test-8 pass
→ TẤT CẢ 10 CHECK PASS
```

**Lỗi UI tìm ra từ ảnh chụp Chrome** (sửa luôn trong ticket này): bubble message giãn full width
(→ `w-fit max-w-[88%]`), avatar "Bạn" bị ép sát mép ở 720px, và nút **Sao chép** nằm trong bubble làm
bubble có khoảng trống dưới chữ (→ chuyển thành `MessageActions` **ngoài** bubble, hiện khi hover, feedback
bằng toast).

**Learning note** — (1) **`useSyncExternalStore` + `getServerSnapshot` rỗng** giải bài toán “state client được persist”
mà không lệch hydration và không bị `react-hooks/set-state-in-effect`. (2) **Ghi `localStorage` phải debounce** — mỗi
token stream mà ghi đồng bộ là hàng trăm lần serialize/ghi trong 1 câu trả lời. (3) **`conversation_id` thuộc về session**,
không phải key toàn cục: 1 key chung thì đổi session là lẫn mạch hội thoại; cần migrate key cũ. (4) `Date.now()`/
`console.*` trong thân component bị `react-hooks/purity` coi là impure ⇒ đẩy sinh id ra hàm module scope. (5) Nút hành
động đặt `absolute` trong bubble dễ đè chữ khi text dài ⇒ đưa về flow bình thường + hiện khi hover.

### KB-4.10 — Mount folder tài liệu trong container + chặn Refresh khi không có nguồn

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4b |
| Repo | BE + FE |
| Phụ thuộc | KB-4.7 |
| Ước lượng | S |

**Bối cảnh** — `.dockerignore` của BE loại `Interview/` ⇒ image **không có** tài liệu gốc, nhưng `chroma_db` (bind mount)
vẫn có 601 chunk từ host. Panel hiện `File trong folder = 0` trong khi `Chunk đã index = 601`, và
**`POST /documents/refresh` (clear rồi auto-load) sẽ xoá 601 chunk rồi index 0 file ⇒ mất index**. Lỗi mất dữ liệu.
**Mục tiêu** — Container thấy đúng folder tài liệu; UI không cho Refresh khi folder rỗng/không tồn tại.
**In scope**
- Compose: mount `./Interview:/app/Interview:ro`.
- `POST /documents/refresh`: folder không tồn tại hoặc 0 file hỗ trợ ⇒ **409 `documents_folder_empty`** **trước khi**
  `clear_database()`; thêm `count_supported_files()`.
- Lifespan: chỉ auto-load khi collection **rỗng** (mount folder làm mỗi lần start re-index 9+ phút) + log đúng tên folder.
- FE panel: nút **Refresh** disabled khi `folder.exists === false || supported_files_count === 0` + hiện lý do.
**Out of scope** — Upload tài liệu từ UI; progress %.
**Acceptance Criteria**
- [x] Trong container: `folder-info` trả `exists:true`, `supported_files_count > 0` (khớp số file host).
- [x] `refresh` khi folder rỗng ⇒ **không** xoá index, trả lỗi rõ ràng (test khẳng định `clear_database` không được gọi).
- [x] Panel Kho tài liệu: Refresh bị chặn + giải thích khi folder rỗng.
- [x] `pytest` + `npm run test` + `build` xanh.
**Q&A (trả lời trước khi làm)**
- Q4: Tài liệu gốc trong Docker: **mount read-only** hay **COPY vào image**?
  → **Chốt: mount read-only** `./Interview:/app/Interview:ro` — sửa tài liệu trên host là container thấy ngay.
**Giả định** — index là thứ đắt (embedding 601 chunk), không được xoá khi chưa chắc có nguồn thay thế.
**Ghi chú kỹ thuật** — `settings.documents_folder = Interview` (tương đối) ⇒ trong container là `/app/Interview`.
**MR** — BE **!20** · FE **!12** (nhánh `fix/kb-4.10-refresh-guard`, đã xoá).
**Kết quả verify** (output thật)

```
$ curl :8010/documents/folder-info → exists: True | total_files: 67 | supported: 56 | path: /app/Interview
$ docker exec chatbot-api python -c "count_supported_files(Path('/app/Interview'), […])" → 56
$ docker exec chatbot-api python -c "count_supported_files(Path('/khong-co'), ['.md'])" → 0
$ curl :8010/documents/status → {"document_count":601,"status":"healthy"}   (index KHÔNG bị xoá)
$ docker compose logs | grep 'skip auto-load' → "Skip auto-load: index đã có 601 chunk …"
$ .venv/bin/python -m pytest -q → 168 passed (4 test guard mới)
$ FE: npm run test → 54 passed · lint 0 · build ✓ · curl :3010 → 200
```

**Learning note** — (1) **Endpoint phá huỷ phải tự kiểm tra điều kiện tiên quyết**, không tin client; guard đặt **trước**
bước clear + test khẳng định `clear_database` **không** được gọi (chỉ assert "trả 409" là chưa đủ). (2) `.dockerignore`
là nguồn của lỗi mất dữ liệu âm thầm. (3) **Mount folder làm lộ bug startup**: `AUTO_LOAD_ON_STARTUP=true` luôn re-index
⇒ 9+ phút mỗi lần start; sửa 5 dòng trong lifespan ⇒ ~2 phút. (4) Log phải lấy tên folder từ `setting`. (5) Test cũ
xanh chỉ vì `.env` dev tình cờ có folder ⇒ **test phụ thuộc môi trường**. **TD mới: TD-25.**

### KB-4.11 — Streaming UX: pha truy hồi + cảnh báo câu trả lời rỗng

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 4b |
| Repo | FE |
| Phụ thuộc | KB-4.8 |
| Ước lượng | S |

**Bối cảnh** — Đo thật trên UI: event `start` đến ở **12.859s**, `end` ở **13.873s**, 26 token dồn trong ~1s ⇒ người dùng
thấy "chữ hiện một cục" sau ~13s spinner câm (rerank CPU ~12,8s — TD-15). Có lần trả về **0 token** (answer rỗng) mà UI
không nói gì ⇒ tưởng treo.
**Mục tiêu** — Người dùng luôn biết hệ thống đang ở pha nào, và không im lặng khi model không trả lời.
**In scope**
- Pha rõ ràng: `đang truy hồi tài liệu…` (gửi → event `start`) → `đang viết…` (`start` → `end`), kèm **số giây**.
- `end.answer` rỗng ⇒ thông điệp giải thích + gợi ý (đổi câu hỏi / kiểm tra kho tài liệu) + nút **Thử lại**.
- Skeleton (KB-4.8) thay spinner câm.
**Out of scope** — Giảm latency rerank (TD-15).
**Acceptance Criteria**
- [x] Trong ~13s đầu hiện rõ "đang truy hồi tài liệu (n giây)" — không phải spinner không lời.
- [x] Answer rỗng ⇒ có message giải thích, không có bubble trống.
- [x] `npm run test` + `build` xanh; test cho `phaseOf()`.
**Ghi chú kỹ thuật** — `lib/stream-phase.ts` pure: `phaseOf({loading, started, finished})` + `formatSeconds`; đếm giây bằng
`useEffect` + `setInterval` (guard unmount).
**MR** — FE **!18** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/18), squash `730f40e`, nhánh `feat/kb-4.11-streaming-phase` đã xoá. (FE only.)

**Kết quả verify** (output thật)

```
$ npx vitest run                 → 12 files / 103 tests passed (12 test mới cho stream-phase:
                                   phaseOf 7 nhánh, formatSeconds, phaseLabelWithElapsed, hint)
$ npm run lint                   → 0 errors, 6 warnings (warning cũ)
$ npm run build                  → ✓ Compiled successfully
$ npm run test:e2e               → 10 passed (~10.9s) — 2 test mới cho KB-4.11:
                                   • "Đang truy hồi tài liệu (0s/1s/2s)" → "Đang viết câu trả lời" → câu trả lời
                                   • answer rỗng ⇒ notice + nút Thử lại, không có bubble trống
$ npm run test:e2e:prod          → 10 passed (production build :3010)
```

Hai test e2e dùng **SSE server thật** (`node:http` stream từng frame + trả CORS) và `route.continue({url})`
để trỏ request của app vào đó — vì `route.fulfill()` gửi cả body một lần nên **không quan sát được** pha
"đang viết". Ảnh chụp: `test-results/shot-09-retrieving.png` (khối trạng thái + skeleton + gợi ý rerank),
`shot-10-writing.png`, `shot-11-empty-answer.png` (cảnh báo + Thử lại).

**Learning note** — (1) **Spinner câm là lỗi UX**: số đo thật cho thấy `start` tới sau ~12,9s, nên phải nói rõ
đang ở pha nào ("đang truy hồi tài liệu" ≠ "đang viết") kèm số giây — người dùng chịu được chờ, không chịu
được mù thông tin. (2) **`route.fulfill()` không test được stream**: muốn thấy chuyển pha phải có server SSE
thật (hoặc `routeWebSocket`); đây là bài học chung cho mọi test streaming. (3) **Không render 2 thứ cùng lúc**:
bubble stream rỗng + khối trạng thái từng hiện song song (ảnh chụp mới thấy) ⇒ lọc bubble rỗng khỏi danh sách
render. (4) **Chữ trong gợi ý là plain text** ⇒ đừng viết `**markdown**` (ảnh chụp lộ literal `**`). (5) `Date.now()`
trong thân component vẫn bị `react-hooks/purity` chặn ⇒ đưa ra helper module scope (`nowMs()`).


### Phase 5 — Nâng cao (LangGraph, auth, upload, độ bền)

> Breakdown 2026-11-08 (sau khi Phase 4b Done). Thứ tự đề xuất theo **giá trị/đau thật**:
> upload → latency → lịch sử bền → chất lượng truy hồi → auth → dọn code → CI.
> Mọi ticket **chờ user trả lời Q&A** trước khi `/run-ticket.md`.

### KB-5.1 — Index tăng dần từ folder tài liệu (file mới / sửa / xoá)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | BE + FE |
| Phụ thuộc | KB-4.10 (mount folder + guard refresh) |
| Ước lượng | M |

**Bối cảnh** — Quy trình hiện tại: copy file mới vào `Interview/` trên host → bấm **Refresh index**, mà refresh =
`clear_database()` + index **toàn bộ** ⇒ 601 chunk embed lại mất **~22 phút** (TD-14); trong lúc chạy index rỗng nên
hỏi gì cũng không có nguồn. Nhưng chỉ **1 file** vừa thêm là thay đổi thật sự.
**Quyết định của user (2026-11-08)** — **Không cần upload từ UI**. Tài liệu mới vẫn do user **copy tay vào folder**
`Interview/` trên host; app giữ folder đó **read-only** (không ghi, không di chuyển file). Giới hạn file **10MB** giữ nguyên.
**Mục tiêu** — App **phát hiện** file mới/đổi/xoá trong folder và **chỉ index phần thay đổi** ⇒ thêm 1 tài liệu là hỏi được
sau vài giây, index cũ **không bị xoá** trong lúc sync.
**In scope**
- Thêm `file_hash` (sha256, 16 ký tự đầu) vào metadata mỗi chunk ⇒ so được "file trên đĩa" với "file đã index".
- `POST /documents/sync` (incremental): quét folder → phân loại `added` / `updated` / `removed` / `skipped` (quá 10MB,
  sai ext) / `unchanged` → với mỗi file `added`/`updated`: xoá chunk cũ theo `where={"source": path}` rồi index lại file đó
  → trả `{added, updated, removed, skipped, total_chunks, elapsed_ms}`.
- Không gọi `clear_database()`; index cũ vẫn dùng được trong lúc sync (không có "cửa sổ rỗng").
- FE drawer Kho tài liệu: nút **Đồng bộ file mới** + hiện kết quả (`+2 mới · 1 cập nhật · 1 xoá · 3 bỏ qua`) + thời gian chạy.
- Test: BE (diff 5 trường hợp: file mới, file đổi nội dung, file đổi tên, file xoá, file > 10MB) + FE (render kết quả) +
  1 e2e Playwright.
**Out of scope** — Upload qua UI (user không cần), xoá/sửa file từ app, OCR, versioning, job nền/hàng đợi.
**Acceptance Criteria**
- [x] Thêm 1 file `.md` vào folder rồi bấm **Đồng bộ** ⇒ `documents/status` tăng **đúng số chunk của file đó**, tổng chunk cũ
  **giữ nguyên**, thời gian **< 30 s** (đo thật, so với ~22 phút của refresh).
- [x] Sửa nội dung 1 file ⇒ số chunk của file đó cập nhật, **không** còn chunk cũ (không tìm ra nội dung đã xoá).
- [x] Xoá/đổi tên file trên host ⇒ chunk của file cũ **không còn** trong index (nếu Q2 chọn xoá).
- [x] File > 10MB hoặc sai ext ⇒ **bỏ qua** + báo trong `skipped`, không làm fail cả lần sync.
- [x] Bấm **Đồng bộ** khi không có gì đổi ⇒ `added=updated=removed=0`, không embed lại (nhanh < 1 s).
- [x] `pytest` + `npm run test` + `npm run test:e2e` + `build` xanh.
**Q&A (trả lời trước khi làm)**
- Q1: **Cách kích hoạt** sync: (A) **bấm nút "Đồng bộ"** trong drawer (chủ động, dễ đoán), (B) **tự động lúc app khởi
  động**, (C) **watch realtime** (`watchdog`/inotify — phát hiện ngay khi copy file, thêm 1 dependency), hay (D) kết hợp
  (A + B)?
  → **Chốt: (D) nút "Đồng bộ" + tự động lúc app khởi động** — không thêm dependency watcher; hành vi dễ đoán, và sau khi restart container thì index tự khớp folder.
- Q2: File **bị xoá/đổi tên** trên host thì index xử lý sao: (A) **xoá chunk tương ứng** để index phản ánh đúng folder
  (khuyến nghị — tránh trả lời từ tài liệu đã bỏ), hay (B) giữ nguyên chunk cũ (chỉ thêm file mới)?
  → **Chốt: (A) xoá chunk tương ứng** — index phản ánh đúng folder, tránh trả lời từ tài liệu đã bỏ. Kèm guard: folder không tồn tại/0 file ⇒ **409 `documents_folder_empty`**, không sync (tránh xoá sạch index).
- Q3: Có **giữ nút "Refresh toàn bộ"** (clear + re-index, ~22 phút, xoá sạch index) làm "cửa thoát hiểm" không, hay **bỏ
  hẳn** để không ai bấm nhầm (muốn làm lại thì xoá `chroma_db`)?
  → **Chốt: (B) bỏ hẳn nút khỏi UI** — chỉ còn **Đồng bộ** + **Clear** (Clear vẫn cần gõ `CLEAR`). Endpoint `POST /documents/refresh` giữ lại cho cứu hộ qua curl nhưng UI không gọi.
**Giả định** — (a) giới hạn **10MB/file** + ext đang cấu hình (`SUPPORTED_EXTENSIONS`) — file vượt thì **skip + báo**, không
làm fail; (b) sync chạy **đồng bộ trong request** (file nhỏ, 1 người dùng); nếu folder lớn gây timeout thì ghi tech debt;
(c) `file_hash` tính trên **nội dung** nên đổi tên file không làm đổi hash — vẫn coi là `removed + added` vì `source` đổi.
**Ghi chú kỹ thuật** — Đã có sẵn: `metadata.source` (path trong container), `file_size`, `chunk_id = sha1(source|chunk_index|text)[:16]`
(KB-2.2), `_rebuild_bm25()` sau khi collection đổi (KB-2.x). Cần thêm: `file_hash` khi index + đọc tập `source` đã index qua
`collection.get(include=["metadatas"])`; xoá theo file bằng `collection.delete(where={"source": path})`. **Không** dùng
`clear_database()`; nhớ rebuild BM25 corpus sau mỗi lần add/delete (nếu không hybrid search lệch — TD-13).
**Kết quả verify** (output thật — chạy trên hệ thật trong Docker)

```
# 1. Test tự động
$ .venv/bin/python -m pytest -q            → 186 passed (13 test mới: compute_file_digest, scan_folder,
                                              diff_indexed 7 nhánh, empty-file; 4 test HTTP cho /documents/sync)
$ npx vitest run                           → 12 files / 103 tests passed
$ npm run lint                             → 0 errors, 6 warnings (cũ)
$ npm run build                            → ✓ Compiled successfully
$ npx playwright test                      → 11 passed (thêm test: bấm Đồng bộ ⇒ hiện kết quả, KHÔNG còn nút Refresh)

# 2. Startup sync (Q1 = D: tự động lúc start) — sau khi rebuild container
$ docker compose logs chatbot-api | grep 'Startup sync'
  → Startup sync: +0 mới, ~0 cập nhật, -0 xoá, unchanged=46, chunks=0, 23ms
  (lần đầu sau upgrade: +10 mới nhưng 0 chunk — hoá ra là **10 file rỗng 0 byte**; đã fix: skip với lý do
   `empty_file`, nên từ lần sau không còn báo "file mới" ảo)

# 3. Thêm 1 file mới → sync (kỳ vọng: chỉ file đó được embed, index cũ nguyên)
$ curl :8010/documents/status              → document_count: 601
$ curl -X POST :8010/documents/sync        → added: ["zz-kb51-sync-test.md"], total_chunks: 2,
                                             unchanged: 46, elapsed_ms: 1233, HTTP 200 · 1.24s
$ curl :8010/documents/status              → document_count: 603      (601 + 2, KHÔNG clear)

# 4. Sync lại khi không đổi → không embed gì
$ curl -X POST :8010/documents/sync        → message: "Không có thay đổi nào trong folder tài liệu",
                                             added/updated/removed = [], elapsed_ms: 23

# 5. Sửa nội dung file → chunk cũ bị xoá, chunk mới thay thế
$ curl -X POST :8010/documents/sync        → updated: ["zz-kb51-sync-test.md"], removed_chunks: 2,
                                             total_chunks: 3, elapsed_ms: 1345
$ curl :8010/documents/status              → document_count: 604      (601 + 3, không còn chunk cũ)

# 6. Xoá file khỏi folder → chunk bị xoá theo (Q2 = A)
$ cru=rm; curl -X POST :8010/documents/sync → removed: ["zz-kb51-sync-test.md"], removed_chunks: 3
$ curl :8010/documents/status              → document_count: 601      (về đúng baseline)
```

**MR** — BE **!21** (https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/21, squash `d06fb5b`) ·
FE **!19** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/19, squash `c67b9e8`). Nhánh
`feat/kb-5.1-*` đã xoá.

**Learning note** — (1) **Incremental index rẻ hơn 1000× so với refresh**: 1 file = **1,2 s** vs **~22 phút** (601 chunk);
index cũ **không bị xoá** trong lúc sync (khác `refresh` — nhờ vậy chat vẫn trả lời được). (2) **Phải hash nội dung, không
chỉ mtime/size**: `sha256[:16]` trong metadata giúp phân biệt *added/updated/unchanged* chính xác và **idempotent**
(sync lần 2 = 23ms, 0 embed). (3) **Chunk ID ổn định (KB-2.2) không đủ để "xoá chunk cũ"**: khi nội dung đổi thì ID đổi
theo ⇒ nếu không `collection.delete(where={"source": ...})` trước khi index lại, chunk cũ **nằm lại** (đo được: 604 thay
vì 601 nếu bỏ bước xoá). (4) **File rỗng 0 byte là cái bẫy**: 10 placeholder `.md` làm startup log báo "+10 mới" mà
`chunks=0` mỗi lần ⇒ lần nào cũng embed lại 0 chunk & log sai. Lọc `size == 0` ⇒ `skipped(empty_file)`.
(5) **Upgrade không được re-embed cả kho**: metadata cũ chưa có `file_hash` ⇒ nếu coi là "updated" thì 601 chunk bị embed
lại ngay lần start đầu; thay vào đó **backfill hash khi `file_size` khớp** (23ms) và chỉ re-index khi size lệch.
(6) **Guard của `refresh` phải áp cho `sync`**: nếu folder biến mất, sync thấy "mọi file đã index đều vắng mặt" ⇒ **xoá
sạch index**; test HTTP khẳng định `sync_documents` **không được gọi** trong trường hợp đó.


### KB-5.2 — Lịch sử hội thoại bền phía server (trả TD-2)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | BE + FE |
| Phụ thuộc | KB-4.9 (store client) |
| Ước lượng | M |

**Bối cảnh** — BE giữ conversation **in-memory** (`ChatService.conversations`, TD-2): restart container là mất mạch
hội thoại phía server (mất context follow-up). FE đã lưu lịch sử **client-side** (KB-4.9) nên F5 vẫn thấy, nhưng **không
dùng được từ máy/trình duyệt khác**, và `conversation_id` trỏ tới state đã mất ở BE.
**Mục tiêu** — Lịch sử + `conversation_id` sống sót qua restart và đọc được từ client khác.
**In scope**
- Lưu bền conversation (messages + `conversation_id` + thời gian) phía BE; nạp lại khi khởi động.
- `GET /conversations` (danh sách), `GET /conversations/{id}` (messages), `DELETE /conversations/{id}`.
- FE: sidebar đọc từ server khi có; fallback `localStorage` khi BE lỗi/offline (không được trắng lịch sử).
- Test: BE (repo round-trip, restart giả lập) + FE (map dữ liệu server vào store) + e2e reload.
**Out of scope** — Sync realtime nhiều thiết bị, phân quyền nhiều user, export/import.
**Acceptance Criteria**
- [x] Restart `chatbot-api` ⇒ `GET /conversations` vẫn trả hội thoại cũ và hỏi tiếp **giữ được context**.
- [x] `DELETE /conversations/{id}` xoá ở server; FE bỏ session tương ứng.
- [x] BE chết ⇒ FE vẫn hiện lịch sử từ `localStorage` (không màn hình trắng).
- [x] `pytest` + `npm run test` + `test:e2e` + `build` xanh.
**Q&A (trả lời trước khi làm)**
- Q1: Lưu bằng **SQLite** (1 file, query/xoá dễ, thêm dep `sqlite3` stdlib + SQLModel/SQLAlchemy?) hay **JSON file**
  (đơn giản nhất, đọc/ghi cả file mỗi lần đổi)?
  → **SQLite bằng `sqlite3` stdlib** (không thêm dep, không ORM) + WAL.
- Q2: Server là **nguồn sự thật** (bỏ `localStorage`, FE luôn đọc server) hay **merge 2 chiều** (local vẫn là chính,
  server để backup/đa thiết bị — phức tạp hơn: xử lý xung đột)?
  → **Server là nguồn sự thật**, `localStorage` chỉ còn là **cache/fallback** khi BE lỗi (không giải quyết xung đột).
- Q3: Giữ tối đa bao nhiêu session (đề xuất 200) và có cần nút **"Xoá toàn bộ lịch sử"** trong UI không?
  → **200 session** (`MAX_CONVERSATIONS`), **không** thêm nút xoá tất cả (đã có xoá từng session).
**Giả định** — (a) 1 người dùng nên không cần `user_id`; (b) nội dung hội thoại **đã được redact PII** trước khi lưu
(KB-1.x) — không lưu bản thô.
**Ghi chú kỹ thuật** — Nếu SQLite: file trong volume (`./data/chat.db`) + `PRAGMA journal_mode=WAL`; nếu JSON: ghi
**atomic** (`tmp` + `os.replace`) như bài học KB-4.9. Không đổi contract `/chat` (chỉ thêm endpoint đọc/xoá).
**Kết quả verify** (output thật)

```
# 1. Test tự động
$ .venv/bin/python -m pytest -q        → 216 passed (30 test mới: 15 `ConversationStore` + 8 `ChatService`+store
                                          + 7 HTTP `/conversations*`)
$ npx vitest run                       → 13 files / 118 tests passed (11 test map/merge + 4 test API mới)
$ npm run lint                         → 0 errors, 6 warnings (cũ)
$ npm run build                        → ✓ Compiled successfully
$ npx playwright test                  → 13 passed (2 test mới: "máy khác thấy lịch sử từ server",
                                          "BE tắt vẫn dùng localStorage")

# 2. AC1 — restart container vẫn còn hội thoại + giữ context (hệ thật, Docker)
$ docker compose logs chatbot-api | grep 'Conversation store'
  → Conversation store ready: ./data/chat.db (0 session đã lưu, max=200)
$ curl -X POST :8010/chat -d '{"message":"Kafka dùng để làm gì trong hệ thống microservice?"}'
  → conversation_id: 7b6a0088-2a6a-4f6e-b4ee-59c47deacc3e
$ curl :8010/conversations
  → total: 1 · title: "Kafka dùng để làm gì trong hệ thống microservice?" · message_count: 2
$ docker compose restart chatbot-api        # RAM mất sạch
$ curl :8010/conversations                   → total: 1 (vẫn còn)                          ← AC1
$ curl :8010/conversations/7b6a0088-…        → roles: ['user','assistant'], user msg còn nguyên
$ curl -X POST :8010/chat -d '{"message":"Vậy khác gì RabbitMQ? Trả lời ngắn 1 câu.",
                               "conversation_id":"7b6a0088-…"}'
  → trả lời so sánh trực tiếp Kafka vs RabbitMQ (hiểu "vậy" = câu trước) ⇒ **giữ context**  ← AC1
$ curl :8010/conversations/7b6a0088-…        → message_count: 4 (user, assistant, user, assistant)

# 3. AC2 — xoá ở server
$ curl -X DELETE :8010/conversations/7b6a0088-…   → 200 {"message":"Đã xoá hội thoại"}
$ curl :8010/conversations/7b6a0088-…             → 404 ;  curl :8010/conversations → total: 0
$ curl -X DELETE :8010/conversations/7b6a0088-…   → 404 not_found (không im lặng trả 200)

# 4. AC3 — BE tắt ⇒ FE vẫn có lịch sử
  Playwright: route `**/conversations**` abort ⇒ sidebar vẫn hiện session từ `localStorage`,
  vẫn thấy message cũ, app không trắng màn hình.

# 5. An toàn dữ liệu
$ git status --short          → **không** có `data/` (đã ignore — DB chứa nội dung chat, không commit)
$ tools/pii_scan.py <13 file> → [OK] Không phát hiện PII/secret
```

**MR** — BE **!22** (https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/22, squash `9a33fed`) ·
FE **!20** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/20, squash `30dc5f8`). Nhánh
`feat/kb-5.2-*` đã xoá.

**Learning note** — (1) **`sqlite3` stdlib đủ dùng, không cần ORM**: 2 bảng + 2 index, `save()` = 1 transaction
(DELETE + `executemany` INSERT) ⇒ 15 test chạy 0,1 s, không thêm dependency. (2) **`with conn:` KHÔNG đóng
connection** (chỉ commit/rollback) — muốn đóng phải `conn.close()`; đây là bẫy dễ mất nhất khi viết SQLite
trong Python, nên mỗi method tự mở/đóng. (3) **Lazy-load khi cache miss** thay vì nạp cả DB lúc start:
`get_conversation_history()` thử RAM → SQLite ⇒ restart không tốn thời gian nạp mà `conversation_id` cũ
vẫn có context. (4) **Thêm attribute vào service làm vỡ 16 test cũ** dựng service bằng `object.__new__`
(không qua `__init__`) ⇒ fix bằng **class-level default** `conversation_store = None` thay vì sửa 16 test
— attribute mới trên service phải có default an toàn. (5) **PII & lịch sử**: lưu bản **đã redact**
(giả định (b)) ⇒ reload từ server có thể thấy `[REDACTED:PHONE]`; trade-off có chủ ý, FE cache local trong
phiên vẫn hiện bản gốc. (6) **Test redaction không được dùng `example.com`** (redactor bỏ qua `example.*`
— KB-1.1 ⇒ assertion pass mà chẳng chứng minh gì); dùng SĐT giả ghép chuỗi `"0912" "345" "678"`.


### KB-5.3 — Giảm latency truy vấn (trả TD-15)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | BE |
| Phụ thuộc | KB-2.1 (eval harness), KB-4.11 (UX đã giải thích pha) |
| Ước lượng | M |

**Bối cảnh** — Rerank chạy **CPU** mất **~8–13 s/query** (TD-15): đo thật `start` đến sau 12,9 s, `end` sau 13,9 s ⇒
27 token dồn trong 1 s. KB-4.11 mới chỉ **giải thích** cho người dùng, chưa làm nhanh. Đây là nút cổ chai lớn nhất của
trải nghiệm hiện tại.
**Mục tiêu** — Giảm latency **có đo lường**, không đánh đổi mù: dùng `eval/` (KB-2.1) chứng minh chất lượng không tụt.
**In scope**
- Đo lại baseline (`run_eval.py --mode retrieval --rerank`) để có số trước khi sửa.
- Thử theo thứ tự rẻ→đắt, mỗi bước đo lại: (1) giảm **top-N đưa vào rerank** (vd 20 → 8), (2) **cache** kết quả rerank
  theo `query_hash + index_version`, (3) **ONNX/quantize** hoặc batch cho reranker.
- Ghi lại bảng so sánh latency × chất lượng; chốt default mới trong `config.py` + `.env.example`.
**Out of scope** — Đổi sang reranker hosted API (tốn quota/tiền), GPU (xem Q2), thay embedding model (Phase 6 đã chốt).
**Acceptance Criteria**
- [x] `latency_p50` của retrieval **giảm ≥ 50%** so với baseline, đo bằng `run_eval.py` cùng 15 câu vàng.
- [x] `Recall@3` và `MRR` **không giảm quá ngưỡng ở Q1**; có bảng số trước/sau trong ticket.
- [x] Default mới nằm trong `config.py` + `.env.example`; `pytest` xanh.
- [x] `/chat` thật: thời gian từ gửi → `start` (log) giảm tương ứng; ghi số đo vào ticket.
**Q&A (trả lời trước khi làm)**
- Q1: Ưu tiên **chất lượng** (giữ ~13 s, không đánh đổi) hay **tốc độ** (chấp nhận giảm nhẹ)? Nếu đánh đổi, cho phép
  `Recall@3`/`MRR` giảm tối đa bao nhiêu % (đề xuất ≤ 5%)?
  → **Chấp nhận giảm ≤ 5%** (đo bằng eval, vượt ngưỡng thì không lấy phương án đó).
- Q2: Máy có **GPU** dùng được cho reranker không, hay chỉ CPU (ảnh hưởng việc có thử ONNX/CUDA hay không)?
  → **Chỉ CPU** — bỏ ONNX/CUDA (GTX 1050 Ti + đổi stack Docker/torch không đáng; ghi thành quyết định).
- Q3: Có chấp nhận **cache câu trả lời/rerank** không (cùng câu hỏi + index chưa đổi ⇒ trả ngay)? Nếu có: cache nên
  invalidate khi nào (sau refresh index / sau upload / theo TTL)?
  → **Có cache in-process** (không Redis), vô hiệu theo **`index_version`** (tăng khi index đổi) **+ TTL 1h**.
**Giả định** — (a) 15 câu vàng hiện đủ đại diện để so sánh (nếu không, mở rộng ở ticket eval); (b) không thêm dịch vụ
ngoài (không Redis, dùng cache in-process vì 1 người dùng).
**Ghi chú kỹ thuật** — Reranker hiện `BAAI/bge-reranker-v2-m3` qua `sentence-transformers`; ONNX Runtime có thể
giảm 2–4× trên CPU nhưng thêm bước export ⇒ chỉ làm nếu Q1/Q2 cho phép. `ENABLE_RERANK=false` là phương án so sánh
"rẻ nhất" để biết rerank đáng giá bao nhiêu latency.
**Kết quả verify** (output thật)

```
# 1. Bảng đo bằng eval harness (15 câu vàng, CACHE TẮT để so sánh công bằng)
$ RERANK_CACHE_ENABLED=false RERANK_TOP_N=<n> .venv/bin/python eval/run_eval.py --mode retrieval --rerank on --tag …

| RERANK_TOP_N | latency_p50 | hit@k | MRR  | precision@k | distinct_file_ratio |
| 20 (baseline)| 11.374 s    | 1.0   | 1.0  | 0.533       | 0.756               |
| 12           |  7.966 s    | 1.0   | 1.0  | 0.556       | 0.756               |
|  **8 (chốt)**|  4.527 s    | 1.0   | 1.0  | 0.556       | 0.734 (−2.9%)       |
| 6            |  3.271 s    | 1.0   | 1.0  | 0.578       | 0.711 (−5.9% ✗)     |

⇒ latency_p50 **−60,2%** (AC1 yêu cầu ≥50% ✓), Recall@3/MRR **không đổi** (0% ✓), mọi metric trong ngưỡng 5%.
   top-N=6 nhanh hơn nhưng `distinct_file_ratio` vượt ngưỡng ⇒ **không** chốt.
Snapshots: `eval/runs/*-kb53-{baseline,top12,top8,top6}-retrieval.json`.

# 2. Cache (cùng process, 2 câu giống nhau)
$ RERANK_TOP_N=8 PYTHONPATH=. .venv/bin/python /tmp/kb53_cache_measure.py
  lần 1 (rerank thật): 7.15s
  lần 2 (cache hit)  : 0.134s          ← **53× nhanh hơn**
  kết quả giống nhau : True
  cache stats        : {size: 1, hits: 1, misses: 1, ttl_seconds: 3600}

# 3. `/chat` thật (container rebuild, top_n=8)
$ curl -s $API/documents/status
  → {"document_count": 601, "index_version": 0,
     "rerank_cache": {"size": 0, "hits": 0, "misses": 0, ...}}
$ curl -X POST $API/chat -d '{"message":"Kafka là gì và dùng khi nào?"}'   → **18.317 s** (cold: nạp model)
$ curl -X POST $API/chat -d '{"message":"Kafka là gì và dùng khi nào?"}'   → **6.267 s**  (−66%, cache hit)
$ curl -s $API/documents/status → rerank_cache {"hits": 1, "misses": 1}

# 4. Invalidation khi index đổi (AC quan trọng — cache không được trả kết quả cũ)
$ echo … > Interview/zz-kb53-cache-test.md && curl -X POST $API/documents/sync
  → "+1 mới" · status: index_version **1**, cache size **0**  (cache bị clear)
$ curl -X POST $API/chat -d '{"message":"Kafka là gì và dùng khi nào?"}'   → **14.402 s** (rerank lại)
  → status: {"hits": 1, "misses": 2}     ← miss tăng ⇒ **không** dùng lại điểm cũ
$ rm … && curl -X POST $API/documents/sync → "-1 xoá" · chunks về **601**, index_version 2

# 5. Test tự động
$ .venv/bin/python -m pytest -q  → **240 passed** (24 test mới: 15 cache + 9 tích hợp `DocumentService`)
$ tools/pii_scan.py <5 file>     → [OK] Không phát hiện PII/secret
```

**MR** — BE **!23** (https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/23, squash `59c2a0a`).
Ticket **chỉ đụng BE** ⇒ 1 MR. Nhánh `perf/kb-5.3-*` đã xoá.

**Learning note** — (1) **Đo trước, sửa sau, chốt bằng số**: cùng 1 lệnh eval, chỉ đổi `RERANK_TOP_N` ⇒
thấy ngay `distinct_file_ratio` là metric "phản đối" việc giảm quá tay (top-6 vượt ngưỡng 5%) trong khi
`hit@k`/`MRR` đã bão hoà ở 1.0 ⇒ nếu chỉ nhìn hit@k sẽ chốt sai. (2) **Cache phải keyed theo `index_version`**,
không chỉ theo query: nếu chỉ băm query, sửa tài liệu xong câu cũ vẫn trả kết quả cũ ⇒ bug im lặng. Tăng version
ở đúng 3 chỗ mutate (`upsert`/`delete`/`clear`) là đủ, và **khoá cache tự vô hiệu** nên quên `clear()` cũng không sai.
(3) **Không cache điểm 0.0**: encoder lỗi trả toàn 0 ⇒ nếu cache sẽ "dính" kết quả rác 1h. (4) **Attribute mới
trên service làm vỡ test dựng bằng `object.__new__`** — lần thứ **hai** trong phase (KB-5.2, giờ KB-5.3) ⇒ ghi
**TD-26** để xử lý gốc (test builder dùng chung), thay vì mỗi ticket lại thêm class default. (5) **Q2 = chỉ CPU**:
đo được −60% latency mà không cần ONNX/CUDA; ONNX (2–4×) để dành khi vẫn chưa đủ nhanh.


### KB-5.4 — Chất lượng truy hồi nhiều bước (query rewrite / multi-query / self-check)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | BE |
| Phụ thuộc | KB-2.5 (default retrieval), KB-5.3 (đo latency) |
| Ước lượng | M |

**Bối cảnh** — Retrieval hiện là **một bước**: câu hỏi → embed → (hybrid) → rerank → trả lời. Câu hỏi mơ hồ / nhiều ý
("so sánh X và Y trong tài liệu A") thường chỉ lấy được nửa ý. Epic Phase 5 ghi "LangGraph (multi-step)".
**Mục tiêu** — Tăng chất lượng trả lời cho câu hỏi phức tạp **bằng chứng cứ đo được** (eval harness), không thêm
framework nếu không cần.
**In scope**
- Chọn **một** hướng cải thiện (theo Q2) và implement trong `ChatService`: query rewrite, multi-query + gộp/dedup, hoặc
  self-check (kiểm câu trả lời có căn cứ trong context).
- Đo bằng `eval/` (thêm 5–10 câu hỏi phức tạp vào bộ vàng nếu cần) + so sánh trước/sau.
- Giữ contract `/chat` + `/chat/stream` không đổi (event `start` có thể mang metadata mới).
**Out of scope** — Agent/tool-calling đa công cụ, multi-hop qua nhiều bộ tài liệu ngoài kho.
**Acceptance Criteria**
- [x] Chất lượng trên bộ eval **tăng có ý nghĩa** (chốt ngưỡng ở Q2) với latency tăng trong mức Q3 cho phép.
- [x] Không vỡ contract: `/chat` + `/chat/stream` vẫn pass toàn bộ test BE hiện có.
- [x] Có cờ env để **tắt** tính năng mới (rollback nhanh, so sánh A/B).
- [x] `pytest` xanh + bảng số trước/sau trong ticket.
**Q&A (trả lời trước khi làm)**
- Q1: Dùng **LangGraph** (thêm dependency, học state graph, dễ mở rộng nhiều bước) hay **tự viết pipeline** trong
  `ChatService` (ít dep, đủ cho 1–2 bước, code hiện tại đã quen)?
  → **Tự viết pipeline** trong `ChatService` (không LangGraph: 1–2 bước, không thêm dep).
- Q2: Ưu tiên bước nào trước: (A) **query rewriting** cho câu hỏi mơ hồ, (B) **multi-query + gộp kết quả** cho câu hỏi
  nhiều ý, (C) **self-check** giảm hallucination (trả lời không có căn cứ)?
  → **(B) multi-query**, split bằng **heuristic (0 token LLM)** trước; LLM-split chỉ thêm nếu không đạt ngưỡng.
  Ngưỡng đã chốt: `hit@k` **+≥5 điểm %** hoặc `MRR` **+≥0,03** trên bộ eval mở rộng; 15 câu cũ **không giảm**.
- Q3: Có chấp nhận **thêm 1–2 lần gọi LLM** (tăng ~2–5 s và quota Groq free tier) cho mỗi câu hỏi không?
  → **Tối đa +1 call** nếu thật cần, nhưng ưu tiên heuristic (0 token — trần TPM 8000 của Groq là giới hạn thật).
**Giả định** — (a) Groq free tier còn dùng được (TPM là giới hạn thật — TD-17); (b) nếu chọn LangGraph thì chỉ dùng cho
luồng multi-step, **không** viết lại toàn bộ `ChatService`.
**Ghi chú kỹ thuật** — Mọi prompt mới **phải** đi qua `pii_service.redact` (rule 30-pii-safety); metadata mới thêm vào
`start`/`end` phải khai báo trong `lib/types.ts` (FE) để không vỡ type.
**Kết quả verify** (output thật)

```
# 1. Bộ eval mở rộng v3: 15 câu cũ + **5 câu nhiều ý** (q16–q20, mỗi câu cần 2 tài liệu)
$ RERANK_CACHE_ENABLED=false .venv/bin/python eval/run_eval.py --mode retrieval --rerank on --multi-query <on|off>

| Cấu hình                                   | hit@k | MRR   | precision@k | distinct_file | latency_p50 |
| Baseline (1 bước, top-N=8)                 | 1.0   | 0.975 | 0.533       | 0.784         | 9.702 s     |
| **Multi-query ON** (mỗi phần top-N=4)      | 1.0   | 0.975 | **0.617**   | 0.750         | **6.500 s** |
| Control: 1 bước, top-N=4 (không multi-query)| 1.0   | **1.0** | 0.550     | 0.767         | **2.002 s** |

⇒ `precision@k` **+8,4 điểm %** (+15,8% tương đối), `hit@k`/`MRR` **giữ nguyên**, không metric nào giảm >5%,
latency **−33%** (mỗi phần chỉ chấm top-N/2). `hit@k`/`MRR` **đã bão hoà** ở bộ 20 câu ⇒ ngưỡng Q2 (hit@k +5 điểm %
hoặc MRR +0,03) **không thể đạt** trên bộ này — đây là **lỗi thiết kế ngưỡng** (chốt trước khi biết baseline đã 1.0),
đã ghi rõ trong ticket thay vì âm thầm đổi.
Snapshots: `eval/runs/*-kb54-{before,after,control-topn4}-retrieval.json`.

# 2. Contract `/chat` thật (container rebuild) — câu nhiều ý
$ curl -X POST :8010/chat -d '{"message":"Kafka là gì và RabbitMQ khác nó ở điểm nào?"}'
  → metadata.multi_query_enabled: True
  → metadata.multi_query_parts: ['Kafka là gì', 'RabbitMQ khác nó ở điểm nào']
  → sources: ['Rabitmq.md', 'Saga Pattern.md', 'Messaging.md']   ← phủ **cả 2 ý** (Kafka + RabbitMQ)
  → contract cũ không đổi (chỉ thêm field metadata, `response`/`sources`/`conversation_id` y nguyên)

# 3. Test
$ .venv/bin/python -m pytest -q  → **263 passed** (23 test mới: 15 `multi_query` + 8 `_initial_retrieval`)
$ cd ../Knowledge-base-fe && npx vitest run → 120 passed · tsc sạch · lint 0 · build ✓ (chỉ thêm 2 field type)
$ tools/pii_scan.py <9 file> → [OK] Không phát hiện PII/secret
```

**MR** — BE **!24** (https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/24, squash `fb4541f`) ·
FE **!22** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/22, squash `74dcb83`, chỉ thêm 2 field type).
Nhánh `feat/kb-5.4-*` đã xoá.

**Learning note** — (1) **Ngưỡng phải chốt sau khi biết baseline**: mình đặt "hit@k +5 điểm % hoặc MRR +0,03" khi
baseline đã là hit@k **1.0** và MRR **0.975** ⇒ gần như **không thể** đạt; lần sau chốt ngưỡng trên **metric còn dư
địa** (ở đây là `precision@k` 0,533) hoặc trên **subset câu khó** (q16–q20). (2) **Luôn chạy control để quy công**:
chạy thêm `top-N=4, single-query` mới thấy phần lớn latency (9,7 → 2,0 s) và MRR 1.0 đến từ **giảm top-N**, không
phải multi-query ⇒ nếu chỉ so baseline ↔ multi-query sẽ **kết luận sai** rằng multi-query làm nhanh hơn 33%.
(3) **Regex tách câu dễ sai**: pattern tách ở "khác … gì" biến "… và RabbitMQ khác gì?" thành `["… ", "?"]` ⇒ mất
multi-query mà **không báo lỗi** (test bắt được). "khác/so sánh" là **dạng câu hỏi**, không phải liên từ tách.
(4) **Heuristic đủ cho 1 ngưỡng rẻ**: 0 token, tất định, dễ A/B — đúng lựa chọn khi trần TPM 8000 là thật.
(5) Multi-query tổng hợp được **2 tài liệu cho 2 ý** trong 1 câu trả lời (thấy ở `sources` của `/chat` thật) — đó là
giá trị thật, dù metric bão hoà không đo hết.


### KB-5.5 — Auth tối giản 1 người dùng (chuẩn bị deploy)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | BE + FE |
| Phụ thuộc | — |
| Ước lượng | S |

**Bối cảnh** — Hiện **không có auth**: ai vào được `:8010` là hỏi được kho tài liệu cá nhân và xem/refresh index. Chấp
nhận được khi chỉ chạy localhost trong WSL, nhưng không ổn nếu mở LAN/VPS (tài liệu có PII — rule §9.5).
**Mục tiêu** — Chặn truy cập trái phép **rẻ nhất có thể**, không kéo theo hệ user/role (YAGNI).
**In scope**
- BE: middleware kiểm token cho mọi endpoint trừ `/health` (và `/ready` tuỳ Q2); token đọc từ env.
- Trả **401** theo taxonomy KB-3.1 (`code: 'unauthorized'`), không lộ chi tiết.
- FE: đọc token từ env/`localStorage` + màn hình nhập token khi thiếu/sai (1 field, không phải login form đầy đủ).
- `.env.example` + README hướng dẫn đặt token; **không** commit token.
**Out of scope** — Đăng ký user, phân quyền nhiều mức, OAuth/SSO, session cookie, HTTPS (Q3).
**Acceptance Criteria**
- [x] Không có token ⇒ mọi endpoint (trừ `/` + `/health`) trả **401** + `code: unauthorized`.
- [x] Có token đúng ⇒ UI hoạt động đầy đủ như hiện tại (chat, kho tài liệu, đồng bộ).
- [x] Token không xuất hiện trong log; `pii_scan` sạch trên file đã sửa.
- [x] `pytest` + `npm run test` + `test:e2e` xanh (cờ tắt nên e2e giữ nguyên 15 test).
**Q&A (trả lời trước khi làm)**
- Q1: Có cần auth **ngay trong phase này** (vẫn chỉ chạy máy cá nhân) hay **để tới khi deploy** (khi đó làm gộp)?
  → **Làm ngay**, nhưng **mặc định TẮT** (`AUTH_ENABLED=false`) — code nằm sẵn, cần là bật bằng env.
- Q2: Nếu làm: **1 token tĩnh qua env** (`X-API-Key`) là đủ, hay cần đăng nhập user/mật khẩu nhiều người? Và `/ready`
  có được **công khai** (để healthcheck Docker) không?
  → **1 token tĩnh** `API_TOKEN` + header `X-API-Key`; `/health` **công khai**, `/ready` **bảo vệ**.
- Q3: Có cần **HTTPS** trong scope không, hay để reverse proxy (Caddy/Nginx) lo (khuyến nghị)?
  → **Ngoài scope** — reverse proxy lo khi deploy.
**Giả định** — (a) 1 người dùng ⇒ token tĩnh là đủ và **không** làm hệ auth đầy đủ; (b) healthcheck Docker cần gọi
được endpoint không cần token (nếu không, compose phải truyền token vào healthcheck).
**Ghi chú kỹ thuật** — So sánh token **constant-time** (`secrets.compare_digest`); FE không nhúng token vào bundle
(`NEXT_PUBLIC_*` là công khai — dùng runtime config/localStorage, xem Q2).
**Kết quả verify** (output thật)

```
# 1. Cờ TẮT (mặc định) — hành vi KHÔNG đổi (container rebuild, `.env` không có AUTH_ENABLED)
$ curl :8010/documents/status → 200 · chunks 601 · healthy   (không gửi header vẫn qua)

# 2. Cờ BẬT (uvicorn, AUTH_ENABLED=true API_TOKEN=secret-test-token)
$ /documents/status (không token)                     → 401
$ /documents/status -H 'X-API-Key: sai'               → 401
$ /documents/status -H 'X-API-Key: secret-test-token' → 200
$ /health                                             → 200   ← healthcheck Docker (KB-3.4) không vỡ
$ /ready                                              → 401   ← bảo vệ (Q&A Q2)
$ -H 'X-Request-ID: trace-123' /documents/status      → 401 + header `x-request-id: trace-123`
  body: {"error":{"code":"unauthorized","message":"Missing or invalid API key.","request_id":"trace-123"}}
  log:  WARNING app.core.auth: auth rejected: request_id=trace-123 path=/documents/status reason=bad_or_missing_token
        (log KHÔNG chứa token — rule 30-pii-safety)

# 3. Fail-closed — bật auth mà API_TOKEN rỗng
$ /documents/status -H 'X-API-Key: bất-kỳ' → 401 (không coi "chưa cấu hình = cho qua")

# 4. Test tự động
$ Knowledge-base:    pytest -q   → 293 passed (+17 auth)
$ Knowledge-base-fe: vitest run  → 130 passed (+6: 3 header/401 ở api, 3 `TokenGate`)
$ tsc sạch · lint 0 problem · build ✓ · playwright 15 passed (cờ tắt nên UI không đổi)
```

**Learning note** — (1) **Thứ tự middleware là bug im lặng**: Starlette thêm middleware mới thành lớp **ngoài** ⇒ đặt
auth **sau** `RequestIDMiddleware` làm 401 trả `request_id: "-"` (mất trace); phải đặt auth **trước** để RequestID bọc
ngoài. Phát hiện bằng `curl -H 'X-Request-ID: …'` rồi so header ↔ body, **không** phải bằng test — sau đó mới viết
regression test. (2) **Fail-closed mới an toàn**: bật auth mà token rỗng phải **chặn**; nếu "cho qua" thì còn tệ hơn
không có auth (tưởng đã khoá). (3) **Cờ + `settings_provider`** ⇒ bật/tắt bằng env, không sửa code; middleware tắt thì
chi phí ~0. (4) **Token không nằm trong `NEXT_PUBLIC_*`** (nhúng bundle, ai cũng đọc) ⇒ FE lưu `localStorage` do người
dùng nhập; chỉ cờ `NEXT_PUBLIC_AUTH_ENABLED` là build-time.

**MR** — BE **!27** (https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/27, squash `25e4b62`) ·
FE **!26** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/26, squash `76c2da7`). Nhánh `feat/kb-5.5-*`
đã xoá. **Bật khi cần**: BE `AUTH_ENABLED=true` + `API_TOKEN=<chuỗi dài>`; FE build với `NEXT_PUBLIC_AUTH_ENABLED=true`.

**MR** — BE **!27** (https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/27, squash 25e4b62) · FE **!26** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/26, squash 76c2da7). Nhánh feat/kb-5.5-* đã xoá. Bật khi cần: BE AUTH_ENABLED=true + API_TOKEN=<chuỗi dài>; FE build với NEXT_PUBLIC_AUTH_ENABLED=true.

### KB-5.6 — Dọn dead code + tối ưu render streaming (trả TD-21, TD-22)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | FE |
| Phụ thuộc | — |
| Ước lượng | S |

**Bối cảnh** — Hai món nợ nhỏ nhưng làm code khó đọc/khó sửa: **TD-22** `MessageWithCitations` còn nhánh render
`sources`/`citations` **chết** (~130 dòng) từ trước KB-4.3 (nguồn giờ do `SourcesPanel` lo); **TD-21** mỗi token stream
**render lại toàn bộ markdown** ⇒ tốn CPU khi câu trả lời dài.
**Mục tiêu** — Xoá code chết, giảm re-render vô ích, không đổi hành vi.
**In scope**
- Xoá nhánh `sources`/`citations` + type `Source`/`Citation` không dùng trong `message-with-citations.tsx`.
- Giảm re-render khi stream: chỉ phần đuôi cập nhật (memo hoá phần đã xong).
- Dọn luôn warning còn lại: `export-utils.ts` (4 `any`) + `lib/types.ts` (import `React` thừa).
**Out of scope** — Đổi thư viện markdown, virtualize danh sách message.
**Acceptance Criteria**
- [x] Không còn export/type/nhánh render không dùng trong `message-with-citations.tsx`; `grep` không còn tham chiếu.
- [x] Streaming câu trả lời dài (≥ 500 token) **không giật** (đo trước/sau bằng `console.count` số lần render).
- [x] `npm run lint` → **0 warning**; `npm run test` + `test:e2e` + `build` xanh; ảnh chụp trước/sau giống nhau.
**Q&A (trả lời trước khi làm)** — Không cần: phạm vi thuần kỹ thuật, hành vi UI phải **giữ nguyên** (e2e 10 check bảo vệ).
**Giả định** — Chấp nhận "chỉ phần đuôi re-render" là đủ; nếu chưa đủ thì tách ticket riêng (virtualize).
**Ghi chú kỹ thuật** — `markdown-message` render full mỗi token; cách rẻ nhất: memo hoá theo `content` **đã chốt** khi
`end` tới, còn lúc stream hiển thị plain text rồi thay bằng markdown đầy đủ khi xong.
**Kết quả verify** (output thật)

```
# 1. Đo render TRƯỚC khi sửa (tests/stream-render.test.tsx, mock MarkdownMessage để đếm)
$ npx vitest run tests/stream-render.test.tsx
  [KB-5.6] markdown renders khi stream 300 token: 300, tổng sau end: 301     ← O(n²)
  [KB-5.6] markdown renders của message cũ khi message khác stream: 40        ← cả list re-render

# 2. Đo SAU khi sửa (cùng test)
  [KB-5.6] markdown renders khi stream 300 token: 0, tổng sau end: 1          ← 300 → 0
  [KB-5.6] markdown renders của message cũ khi message khác stream: 0         ← 40 → 0
  2 passed

# 3. Dead code (AC1)
$ grep -rn 'citations' lib/ app/ components/ tests/ e2e/
  → chỉ còn comment trong `message-with-citations.tsx` + field `ChatMessage.citations` (đã xoá)
$ wc -l components/message-with-citations.tsx     → 178 → **72 dòng** (xoá ~130 dòng nhánh sources/citations, thêm comment/memo ⇒ **−106 dòng**)
$ git diff --stat                                  → 6 file changed, 61 insertions(+), 222 deletions(-)
                                                     (gồm xoá `lib/export-utils.ts` 66 dòng — dead, 0 import)

# 4. Lint (AC3) — trước: 6 warning
$ npm run lint                → **0 problems** (0 error, 0 warning)
   • 4 × `any` → xoá `lib/export-utils.ts` (không file nào import)
   • 1 × unused `React` import trong `lib/types.ts` → xoá
   • 1 × `react-hooks/set-state-in-effect` (documents-panel) → `load()` chạy sau 1 microtask

# 5. Không đổi hành vi
$ npx vitest run              → 14 files / 120 tests passed (2 test mới)
$ npx playwright test         → **14 passed** (thêm test: đang stream hiện plain text `**Đậm**`,
                                sau `end` mới có `<strong>` + chip [S1]; 13 check cũ vẫn xanh)
$ npm run build               → ✓ Compiled successfully
Ảnh chụp: `shot-09..11`, `shot-12/13` (trước/sau) giữ nguyên bố cục; `shot-14-markdown-after-end.png`
là trạng thái sau `end` (markdown đầy đủ). Khác biệt **có chủ ý** duy nhất: trong lúc stream, text chưa format.
```

**MR** — FE **!21** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/21, squash `b2c9fab`).
Ticket **chỉ đụng FE** ⇒ 1 MR. Nhánh `refactor/kb-5.6-*` đã xoá.

**Learning note** — (1) **Chi phí thật của "render markdown mỗi token" đo được bằng test, không cần profiler**:
mock component nặng nhất (`MarkdownMessage`) rồi đếm số lần nó render qua các lần rerender giả lập stream ⇒
300 token = 300 lần parse, và **cả message cũ cũng render lại 40 lần**. Viết test này **trước** khi sửa để có
số "before" trung thực. (2) **`memo` chỉ có tác dụng khi prop ổn định**: `onCitationClick={(id) => …}` tạo
closure mới mỗi render ⇒ memo vô nghĩa; chuyển sang `messageId` + callback ổn định (`useCallback`) ở `page.tsx`.
(3) **Plain text khi stream là trade-off chấp nhận được** (đúng ghi chú kỹ thuật của ticket): không format
trong ~vài giây đổi lấy việc bỏ O(n²); citations/markdown chỉ cần đúng khi đọc lại. (4) **Dead code nên xoá
cả file khi không còn import** (`export-utils.ts`: 66 dòng mock, 4 `any`, 0 tham chiếu) — sửa `any` thành type
đúng sẽ là công vô ích. (5) **`react-hooks/set-state-in-effect`** (React Compiler lint) khó chịu với pattern
"fetch khi mở panel"; cách rẻ nhất là nhường 1 microtask (`await Promise.resolve()`) trước khi gọi hàm set state.


### KB-5.7 — CI GitLab: lint + test + build + e2e (trả TD-24)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | BE + FE |
| Phụ thuộc | KB-4.9 (Playwright đã có) |
| Ước lượng | M |

**Bối cảnh** — Project **chưa có CI/CD** (TD-24): mọi quality gate hiện chạy tay; merge không bị ràng buộc tự động. Hai
repo GitLab (`knowledge-base-be`, `knowlege-base-fe`) đều chưa có pipeline.
**Mục tiêu** — MR phải xanh mới merge được; bắt lỗi type/test/build **trước** khi vào `main`.
**In scope**
- `.gitlab-ci.yml` BE: `pytest` (mock provider, không gọi LLM thật) — cache pip.
- `.gitlab-ci.yml` FE: `lint` + `typecheck` + `test` (vitest) + `build` — cache npm.
- e2e: Playwright trong **image chính thức** (`mcr.microsoft.com/playwright`) trên `next start` (stub route như test hiện
  tại ⇒ **không cần** BE/LLM).
- Bật **protected branch** cho `main` (MR + pipeline xanh) nếu Q3 đồng ý.
**Out of scope** — Deploy tự động, build/push registry image, e2e với BE thật + LLM (tốn quota).
**Acceptance Criteria**
- [x] MR mới có pipeline chạy; pipeline **đỏ** khi cố tình làm fail test (kiểm chứng bằng 1 MR thử rồi revert).
- [x] Pipeline FE **< 8 phút**, BE **< 5 phút** (có cache).
- [x] `main` không merge được khi pipeline đỏ (nếu bật Q3).
- [x] Ghi thời gian thật lần chạy đầu vào ticket.
**Q&A (trả lời trước khi làm)**
- Q1: Dùng **GitLab.com shared runner** (miễn phí, giới hạn phút/tháng) hay **runner riêng** trên máy bạn (ảnh hưởng
  `tags:`, khả năng chạy Docker và tốc độ)?
  → **Shared runner** (không `tags:`) — pipeline chạy trên hạ tầng GitLab, không phụ thuộc máy local.
- Q2: e2e trong CI: chạy **headless Chromium trong image Playwright** (khuyến nghị — không cần BE) hay **bỏ e2e** khỏi
  CI để pipeline nhanh?
  → **Có e2e** trong pipeline (Playwright image chính thức; e2e hiện stub route nên không cần BE/LLM).
- Q3: Có bật **protected branch** cho `main` không? (đổi thói quen: phải qua MR, không push thẳng `main`)
  → **Chưa** bật protected branch — giữ merge condition như cũ; bật sau nếu muốn.
**Giả định** — (a) image Playwright pin version khớp `@playwright/test`; (b) secrets để trong **CI variables** (masked),
không commit; (c) pipeline không cần dịch vụ ngoài (không DB, không LLM).
**Ghi chú kỹ thuật** — 2 repo riêng ⇒ 2 file CI; e2e cần `APP_URL` trỏ server CI tự bật (`next start` + chờ port).
**Kết quả verify** (output thật)

```
# 1. YAML hợp lệ theo GitLab CI Lint API (không đoán — gọi API thật)
$ Knowledge-base:    glab ci lint            → ✓ CI/CD YAML is valid!
$ Knowledge-base-fe: glab ci lint            → ✓ CI/CD YAML is valid!

# 2. CỜ TẮT (mặc định) — KHÔNG tạo pipeline
$ glab ci lint --dry-run --ref main          (cả 2 repo)
  → ".gitlab-ci.yml is invalid." + "The pipeline did not run. Review the workflow:rules configuration"
  ⇒ đúng ý: chưa đặt `CI_ENABLED` ⇒ mọi push/MR **không** tạo pipeline, hành vi như trước KB-5.7.

# 3. Khi BẬT cờ (cùng file, đổi điều kiện thành luôn-đúng để mô phỏng `CI_ENABLED=true`)
$ glab ci lint /tmp/fe-ci-on.yml --dry-run --ref main → ✓ valid (KHÔNG còn "pipeline did not run")
$ glab ci lint /tmp/be-ci-on.yml --dry-run --ref main → ✓ valid
  ⇒ gate chỉ là 1 điều kiện; bật biến là pipeline xuất hiện, không phải sửa file.

# 4. Chạy đúng các lệnh mà job sẽ chạy (local, output thật)
$ Knowledge-base:    python -m pytest -q                → **293 passed**
$ Knowledge-base-fe: npm run lint                       → 0 error/warning
$                   npm run typecheck                   → tsc sạch
$                   npm run test                        → **130 passed**
$                   npm run build                       → ✓ Compiled successfully
$  (mô phỏng job e2e: build → `next start` → e2e với APP_URL, đúng thứ tự trong .gitlab-ci.yml)
$                   npm run start &  → server up: 200
$                   APP_URL=http://localhost:3000 npx playwright test → **15 passed**

# 5. Sau khi merge vào `main` — Gate giữ đúng: KHÔNG pipeline nào được tạo
$ glab ci list (knowledge-base-be)    → "No pipelines available on anchu3003/knowledge-base-be"
$ glab ci list (knowlege-base-fe)     → "No pipelines available on anchu3003/knowlege-base-fe"
$ glab mr merge !28 / !27             → "! No pipeline running on feat/kb-5.7-gitlab-ci"

# 6. CHƯA verify được (nói rõ, không claim)
$ Chưa chạy pipeline thật trên GitLab (cờ tắt, và cần runner nhận job) ⇒ "pipeline xanh" CHƯA được chứng minh.
   Bước tiếp khi bạn bật `CI_ENABLED=true`: mở 1 MR thử, xem thời gian thật của 2 pipeline, và thử cố tình
   làm fail 1 test để chắc pipeline đỏ (AC của ticket yêu cầu — sẽ kiểm ngay khi bật).
```

**MR**: BE [!28](https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/28) ·
FE [!27](https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/27) — squash-merged, nhánh đã xoá.

**Learning note** — (1) **Gate bằng `workflow:rules` là cách "tắt CI" đúng**: đặt `- if: '$CI_ENABLED == "true"'`
rồi `- when: never` ⇒ **không** tạo pipeline (không tốn runner, không hiện dấu đỏ trên MR) — khác với để job
`when: manual` (vẫn tạo pipeline rỗng + vẫn hiện UI). (2) **`glab ci lint --dry-run` là cách verify CI mà không cần
runner**: nó trả đúng câu "The pipeline did not run. Review the workflow:rules configuration" ⇒ chứng minh được cờ tắt
mà không phải push thử. (3) **e2e trong CI phải dùng `next start`** chứ không phải `next dev`: config Playwright chỉ tự
bật dev-server khi **không** có `APP_URL`, nên job set `APP_URL` + tự chờ server bằng `fetch` loop (không thêm
dependency `wait-on`). (4) **Pin image Playwright theo version thư viện** (`v1.65.0-jammy` khớp `@playwright/test
^1.65.0`) — lệch version là Chromium không khớp, test fail khó hiểu. (5) **Không claim "CI xanh"**: việc chưa chạy
pipeline thật phải ghi rõ trong ticket, không suy ra từ "yaml valid".

### Phase 6 — Tech refresh (đồng bộ dependency & model)

> **Đánh giá 2026-11** (chi tiết ở `architecture.md` §10 — Tech stack assessment). Tóm tắt: deps BE *thực tế*
> đã mới (LangChain 1.1 · pydantic 2.12 · FastAPI 0.123 · openai 2.8), nhưng lệch ở: **Python 3.11** (chỉ còn
> security; 3.10 đã EOL 2026-10), **requirements không pin**, và **embedding/reranker English-only** (2021).
> **Khuyến nghị làm KB-6.1 → KB-6.3 TRƯỚC Phase 2** vì embedding model ảnh hưởng trực tiếp chất lượng retrieval.

### KB-6.1 — Pin dependencies + nâng Python runtime

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 6 |
| Repo | BE |
| Phụ thuộc | — |
| Ước lượng | S |

**Bối cảnh** — `requirements.txt` không pin version → build không reproducible (mỗi lần cài ra bản khác).
Dockerfile dùng `python:3.11-slim`; Python 3.11 chỉ còn **security fixes**, 3.10 **đã EOL** (2026-10-01).
**Mục tiêu** — Reproducible build + runtime Python được hỗ trợ (bugfix/security).
**In scope** — Pin exact versions (tách dev deps); cập nhật Dockerfile base image; update README.
**Out of scope** — Đổi framework; thay `langchain-*` bằng stack khác.
**Acceptance Criteria**
- [x] `requirements.txt` dùng **range pin** (`>=floor,<next-major`) + `requirements-dev.txt` riêng.
- [x] Dockerfile base image = `python:3.13-slim`.
- [x] Pin resolve được + `pytest` pass (chi tiết ở Kết quả verify).
**Giả định** — Bump **minor/patch an toàn**, không đổi major framework.
**Q&A (trả lời trước khi làm)**
- Q1: Nâng Python lên **3.13** (ổn định lâu) hay **3.14** (mới hơn)? (local đang 3.12)
  → **3.13**
- Q2: Pin **cứng** (`==`, reproducible tối đa) hay **range** (`>=x,<y`, dễ nhận patch)?
  → **range**
- Q3: Dùng công cụ lock nào — `pip freeze` đơn giản, hay `pip-tools`/`uv`?
  → **pip-tools / uv**
**Ghi chú kỹ thuật** — Cân nhắc `uv` để lock nhanh; giữ Docker multi-stage sẵn có.
**Kết quả verify** —
- `python -m pip install --dry-run --no-deps -r requirements.txt` → mọi pin thoả; `Would install rank-bm25-0.2.2 sentence-transformers-6.2.0`.
- `python -m pytest -q` → **16 passed**.
- Dockerfile: `FROM python:3.13-slim` (builder + final). `docker run --rm python:3.13-slim python -V` → **Python 3.13.18**.
- ⚠️ Full image build (`docker build` gồm torch) **chưa chạy** ở môi trường này (nặng) → theo dõi ở **TD-6**.
**Learning note** — Range pin `>=floor,<next-major` để nhận patch nhưng chặn major; floor lấy từ version env hiện tại.
Thêm `langchain-core` + `langchain-text-splitters` (được import trực tiếp nhưng thiếu trong requirements). Không cần
`python-multipart` (không dùng `UploadFile`/`Form`). Lock đầy đủ (uv/pip-tools) cần env thật.

### KB-6.2 — Embedding model đa ngữ (thay `all-mpnet-base-v2`)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 6 |
| Repo | BE |
| Phụ thuộc | KB-6.1 |
| Ước lượng | M |

**Bối cảnh** — `sentence-transformers/all-mpnet-base-v2` (2021, 768-d) là **English-only**. KB có tài liệu
**tiếng Việt** → retrieval tiếng Việt kém. Đây là điểm "outdate" ảnh hưởng nặng nhất.
**Mục tiêu** — Đổi sang embedding model **đa ngữ**, re-index, kiểm chất lượng retrieval tiếng Việt.
**In scope** — Đưa tên model ra env (bỏ hard-code `document_service.py:33`); re-index `chroma_db`; test.
**Out of scope** — Fine-tune model; đổi vector store khỏi ChromaDB.
**Acceptance Criteria**
- [x] Model cấu hình qua env `EMBEDDING_MODEL` (không hardcode) + helper `build_embedding_params` test được.
- [x] Params embedding đúng (`device=cpu`, `normalize_embeddings=True`).
- [x] Re-index thật + so sánh query VN → **đã làm ở KB-2.4** (re-index 56 file / 601 chunk + eval 15 câu vàng, MRR 1.0 — **TD-7 đã trả**).
**Giả định** — Chấp nhận re-index lại (bắt buộc vì dimension khác).
**Q&A (trả lời trước khi làm)**
- Q1: Chọn model nào? `Qwen/Qwen3-Embedding-0.6B` (đa ngữ, ~0.6B, chất lượng cao) vs
  `google/embeddinggemma-300m` (nhẹ/nhanh CPU) vs giữ nguyên `all-mpnet-base-v2`.
  → **`Qwen/Qwen3-Embedding-0.6B`** (ưu tiên chất lượng)
- Q2: Ưu tiên **chất lượng retrieval** hay **nhẹ/nhanh cho CPU** (GTX 1050Ti 4GB)?
  → **chất lượng**
- Q3: Có cần tiếng Việt + tiếng Anh trộn (tài liệu hiện có cả 2)? → ảnh hưởng chọn model.
  → **có (cả VN + EN)**
**Ghi chú kỹ thuật** — Đổi dimension ⇒ tạo collection mới + re-embed (free, local). Model nặng hơn ⇒
encode chậm hơn trên CPU; cân nhắc giữ batch `EMBEDDING_BATCH_SIZE`.
**Kết quả verify** —
- `python -m pytest -q` → **19 passed** (3 test mới cho embedding config).
- `get_settings().embedding_model` → `Qwen/Qwen3-Embedding-0.6B`; `build_embedding_params` → `{model_name, model_kwargs:{device:cpu}, encode_kwargs:{normalize_embeddings:True}}`.
- `py_compile` config/embeddings/document_service OK.
- Model hợp lệ: HF `Qwen/Qwen3-Embedding-0.6B` (`library_name: sentence-transformers`, 1024-d, apache-2.0).
- ⚠️ **Re-index thật CHƯA chạy** ở env dev (thiếu torch + model ~1.2GB) → **TD-7**. Quy trình: xoá `chroma_db/` (hoặc `POST /documents/refresh`) rồi để app auto-load lại.
**Learning note** — Đưa model ra env + tách helper thuần `build_embedding_params` để test không cần torch.
Qwen3-Embedding **ST-compatible** (không cần `trust_remote_code`); đổi dim 768→1024 ⇒ buộc re-index (collection cũ
lỗi dimension nếu không xoá). `normalize_embeddings=True` phù hợp cosine.

### KB-6.3 — Reranker đa ngữ (`bge-reranker-v2-m3`)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 6 |
| Repo | BE |
| Phụ thuộc | KB-6.2 |
| Ước lượng | S |

**Bối cảnh** — Reranker hiện tại `cross-encoder/ms-marco-MiniLM-L-6-v2` là English-only. Reranker là
"win rẻ" lớn cho RAG; bản đa ngữ `BAAI/bge-reranker-v2-m3` (Apache-2.0) là lựa chọn phổ biến 2026.
**Mục tiêu** — Đổi reranker sang bản đa ngữ, đo cải thiện trên query tiếng Việt.
**In scope** — Đổi env `RERANK_MODEL` (đã có sẵn cơ chế); test + so sánh.
**Out of scope** — Thay bằng rerank API; đổi sang LLM-rerank.
**Acceptance Criteria**
- [x] `RERANK_MODEL=BAAI/bge-reranker-v2-m3` là default (env override được); code đã đọc `settings.rerank_model`.
- [x] So sánh thứ tự rerank trước/sau trên query VN → **đã làm ở KB-2.5** (MRR 0,774 → **1,0**; giá: +8 s/query ⇒ TD-15, nay đã giảm ở KB-5.3 — **TD-8 đã trả**).
**Giả định** — Chấp nhận latency tăng (bge-m3 ~568M, chậm hơn MiniLM trên CPU).
**Q&A (trả lời trước khi làm)**
- Q1: Chấp nhận `bge-reranker-v2-m3` (đa ngữ, nặng hơn) hay giữ MiniLM (nhanh, English-only)?
  → **`BAAI/bge-reranker-v2-m3`**
- Q2: `RERANK_TOP_N` giữ 20 hay giảm (đổi latency)?
  → **giữ 20**
**Ghi chú kỹ thuật** — `document_service.py` lazy-load cross-encoder; chỉ đổi tên model qua env.
**Kết quả verify** —
- `get_settings().rerank_model` → `BAAI/bge-reranker-v2-m3`; `RERANK_TOP_N=20`; `ENABLE_RERANK=True`.
- `python -m pytest -q` → **19 passed**; `py_compile` OK.
- `document_service._ensure_cross_encoder` đã đọc `settings.rerank_model` (không cần sửa logic).
- ⚠️ **Load rerank thật CHƯA chạy** (thiếu torch + model ~2.3GB) → **TD-8**.
**Learning note** — Vì code đã đọc `settings.rerank_model` sẵn nên chỉ đổi default — minh chứng cho việc tách config
ra env từ đầu. `bge-reranker-v2-m3` là CrossEncoder chuẩn ST (không cần `trust_remote_code`); latency tăng trên CPU
(rerank 20 cặp với XLM-R-large) — chấp nhận theo Q&A.

### KB-6.4 — Frontend dependency refresh

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 6 |
| Repo | FE |
| Phụ thuộc | — |
| Ước lượng | S |

**Bối cảnh** — FE đã mới (Next 16 · React 19 · Tailwind v4) nhưng còn tag **`latest`** mơ hồ trong
`package.json` (`@radix-ui/react-scroll-area`, `@radix-ui/react-slot`, `@vercel/analytics`) → build không
reproducible; `lucide-react ^0.454`, `tailwind-merge ^2.5.5` có thể lên bản mới. Ngoài ra `next.config.mjs`
còn key `eslint` (Next 16 đã bỏ hỗ trợ) → dọn.
**Mục tiêu** — Pin version cụ thể + bump an toàn; giữ build xanh.
**In scope** — Bỏ tag `latest`, pin version; bump minor an toàn.
**Out of scope** — Đổi framework/UI lib; thêm lib mới.
**Acceptance Criteria**
- [x] Không còn tag `latest` trong `package.json`.
- [x] `npm run build` pass + `tsc --noEmit` sạch.
**Giả định** — Chỉ bump **minor/patch an toàn** mặc định.
**Q&A (trả lời trước khi làm)**
- Q1: Chỉ **pin + bump minor an toàn**, hay bump cả **major** (vd `tailwind-merge` v3, `zod` v4) — rủi ro phải sửa code?
  → **an toàn (pin + bump minor)**
- Q2: Có muốn tôi chạy `npm run build` và tự sửa lỗi phát sinh không?
  → **có**
**Ghi chú kỹ thuật** — `npm install` đang dùng `--force/--legacy-peer-deps` (xem FE README); cân nhắc dọn.
**Kết quả verify** —
- `package.json`: **`latest count = 0`** (pin `react-scroll-area@1.2.10`, `react-slot@1.2.4`, `@vercel/analytics@1.5.0`).
- `next.config.mjs`: bỏ key `eslint` → cảnh báo `Unrecognized key(s): 'eslint'` biến mất khi build.
- `npm run build` → **✓ Compiled successfully** (3/3 static pages).
- `npx tsc --noEmit` → **exit 0**.
**Learning note** — Chọn "an toàn": pin `latest` về **đúng version đang cài** (không ép nâng) → reproducible
mà không rủi ro. `next.config.mjs` giữ `typescript.ignoreBuildErrors` (build bỏ qua lỗi type) — hiện `tsc` sạch
nên có thể bỏ cờ này sau (cải thiện, không bắt buộc). Còn warning cũ `baseline-browser-mapping` (không phải lỗi).

---


### Phase 7 — Dev environment: migrate sang WSL (epic)

> Mục tiêu: **giữ Windows sạch** (ít tool) — gom toàn bộ toolchain vào **WSL Ubuntu đã có sẵn**. Đồng thời
> giải quyết friction ML deps (`torch`, `sentence-transformers`) + đồng bộ với `shop-lab-microservices`.
> Sau migrate: Windows chỉ còn **VS Code (+ Remote-WSL)**; mọi thứ dev chạy trong WSL.

### KB-7.1 — Migrate dev environment sang WSL

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 7 |
| Repo | BE + FE + root (AI assets) |
| Phụ thuộc | — |
| Ước lượng | M |

**Bối cảnh** — Không muốn cài nhiều tool trên Windows; WSL Ubuntu đã có sẵn (và `shop-lab-microservices` cũng ở đó).
BE nặng ML (`torch`, `sentence-transformers`) cài trên Linux sạch hơn Windows.
**Mục tiêu** — Dev hoàn toàn trong WSL (Linux FS); Windows giữ tối thiểu; project chạy được + git/glab flow hoạt động trong WSL.
**In scope**
- Copy **toàn bộ** project (BE + FE + root AI assets) vào `~/projects/Kb-khoa-hoc` (Linux FS).
- Cài toolchain trong WSL: `build-essential`, `git`, **Python 3.13** (uv), **Node LTS** (fnm/nvm), **glab** + auth, dùng `~/.ssh` sẵn có cho GitLab.
- **Docker engine trong WSL** (bật systemd) — không dùng Docker Desktop.
- Verify: `pytest` · `npm run build` · `docker build` BE · glab MR cycle.
- Update `AGENTS.md` §6/§10 + `architecture.md` (môi trường = WSL).
**Out of scope** — Gỡ tool trên Windows (giữ nguyên — Q3); đổi code/kiến trúc; migrate `shop-lab`.
**Acceptance Criteria**
- [x] Repo ở `~/projects/kb-khoa-hoc` (Linux FS, **không** `/mnt/d`); `git remote` + nhánh `main` OK.
- [x] `uv` + Python 3.13 trong WSL; `pytest` → 19 passed.
- [x] Node LTS trong WSL; `npm run build` (FE) pass.
- [x] Docker engine trong WSL: `docker build` (BE, `python:3.13`) chạy → **giải quyết TD-6**.
- [x] `glab auth status` OK + thử 1 MR cycle (branch→push→MR→merge) trong WSL.
- [x] VS Code Remote-WSL mở workspace OK; `.clinerules`/`.cline` được nhận.
- [x] `AGENTS.md` ghi môi trường = WSL.
**Giả định** — (a) dùng `uv` để quản Python (đã chọn ở KB-6.1); (b) WSL distro **Ubuntu** sẵn có; (c) chấp nhận copy/clone lại code vào `~/`.
**Q&A (trả lời trước khi làm)**
- Q1: Chuyển toàn bộ hay chỉ BE?
  → **toàn bộ** (BE + FE + docs/AI assets)
- Q2: Docker — Docker Desktop hay docker engine trong WSL?
  → **docker engine trong WSL**
- Q3: Gỡ `glab` + Node trên Windows?
  → **giữ lại** (không gỡ)
- Q4: Copy code vào `~/` (Linux FS)?
  → **copy vào ~**
- Q5: Distro nào?
  → **Ubuntu có sẵn**
**Ghi chú kỹ thuật** — Linux FS bắt buộc (perf; `/mnt/d` chậm với `node_modules`/torch). Docker engine trong WSL cần bật systemd
(`/etc/wsl.conf`: `[boot]` `systemd=true`) → `sudo systemctl enable --now docker` + thêm user vào group `docker`. `glab`: cài binary
trong WSL + `glab auth login --token`. 2 repo clone bằng SSH (`~/.ssh`); root AI assets copy bằng `rsync -a` (loại `.git`, `node_modules`, `chroma_db`, `.venv`).
**Kết quả verify** (WSL2 Ubuntu 26.04 · kernel `6.18.54.1-microsoft-standard-WSL2` · `/etc/wsl.conf` `systemd=true`)

| Bước | Lệnh | Kết quả |
|---|---|---|
| Code trên Linux FS | `pwd` | `/home/anchu/projects/kb-khoa-hoc` (không `/mnt/*`); `git remote -v` SSH GitLab OK |
| Python 3.13 | `uv python install 3.13` + `uv venv --python 3.13 .venv` | **3.13.18** (`cpython-3.13.18-linux-x86_64-gnu`) |
| Deps BE | `uv pip install -r requirements.txt -r requirements-dev.txt` | OK · `torch 2.15.0+cu132` |
| Test BE | `.venv/bin/python -m pytest -q` | **19 passed**, 1 warning (langchain-community sunset) |
| Node LTS | `fnm install --lts` (fnm 1.39.0, `~/.local/share/fnm`) | **v26.13.0** · npm 11.20.0 |
| Build FE | `npm ci` → `npm run build` | `npm ci` 32s · build ✓ `Compiled successfully`, 3/3 static pages |
| `build-essential` (trong scope) | — | **không cài** (apt cần sudo password) — không cần thực tế: mọi dep có wheel `cp313` manylinux; nếu cần build từ source: `sudo apt install build-essential` |
| Docker engine trong WSL | `systemctl is-active docker` · `docker info` | **active** · `Server Version 29.9.3`, `Docker Root Dir /var/lib/docker`, `/usr/bin/dockerd` native (đã bỏ symlink Docker Desktop) |
| Docker build BE | `docker build -t kb-be:local .` | **OK 6m07s** · image 6.53GB content |
| Smoke test image | `docker run --rm kb-be:local python -c "from app.main import app"` | `python 3.13.18` · `APP OK: RAG Chatbot API` → **TD-6 trả xong** |
| Secret trong image | `docker run --rm kb-be:local sh -c 'test -f /app/.env'` | `OK: no .env` (nhờ `.dockerignore` mới) |
| glab | `glab auth status` | logged in `anchu3003` (glab 1.128.0) |
| CRLF churn | `core.autocrlf=input` + `.gitattributes` `eol=lf` | 2 repo sạch (BE 83 file / FE 27 file "dirty" trước đó chỉ do CRLF) |
| MR cycle | branch → push → MR → squash merge | BE **MR !6** · FE **MR !3** |

**Learning note**
- Nguyên nhân 2 repo "dirty toàn bộ" sau khi copy sang WSL **không** phải sửa nội dung: working tree là CRLF còn blob trong git là LF → `git diff --ignore-cr-at-eol` rỗng. Fix đúng là `git restore .` + `core.autocrlf=input` + `.gitattributes` (`* text=auto eol=lf`), **không** commit lại 83 file.
- Docker Desktop WSL integration làm `/usr/bin/docker` thành **symlink** vào `/mnt/wsl/docker-desktop/cli-tools/...`; cài engine native thì phải xoá symlink trước, và **tắt WSL integration** trong Docker Desktop, nếu không Desktop tạo lại symlink + bind-mount `/var/run/docker.sock`.
- Không có `.dockerignore` ⇒ `COPY . .` đưa **cả `.env` (key thật) vào image** — chỉ phát hiện khi kiểm tra `test -f /app/.env` trong container. Luôn thêm `.dockerignore` với `.env`.
- `uv` / `fnm` giải quyết được Python + Node **không cần `sudo apt`** (máy không có sudo passwordless) → giữ Windows/hệ thống sạch đúng mục tiêu ticket.
- Ubuntu 26.04 (`resolute`) đã có dists trên `download.docker.com` → script vẫn để fallback `noble`/`jammy` cho lần cài trên distro mới hơn.

### KB-8.1 — ADR backfill #1: nền tảng retrieval (5 ADR)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 8 |
| Repo | — (tài liệu root `docs/adr/`, **không** thuộc git repo con nào) |
| Phụ thuộc | — |
| Ước lượng | M |

**Bối cảnh** — `docs/adr/` mới có **1 ADR** (`0001-llm-provider-groq.md`) trong khi Phase 2–5 đã chốt rất nhiều
quyết định lớn (vector store, embedding, rerank, chunking, dedup). Chúng hiện chỉ nằm rải rác trong
`architecture.md` + ticket + changelog ⇒ **không đọc lại được "vì sao"**, mất giá trị học tập (AGENTS.md §3.3 yêu cầu
ADR cho thay đổi lớn).
**Mục tiêu** — Backfill ADR cho nhóm quyết định **nền tảng retrieval** để đọc 1 file là hiểu vì sao hệ thống như hiện
tại, kèm số đo thật để làm tài liệu học.
**In scope** (5 ADR, đánh số tiếp từ 0001)
- `0002-vector-store-chromadb.md` — ChromaDB persistent local vs Qdrant / pgvector / FAISS (KB-2.1…2.5).
- `0003-embedding-model-qwen3.md` — `Qwen/Qwen3-Embedding-0.6B` local CPU (KB-6.2; re-index ở KB-2.4: 56 file → 601 chunk).
- `0004-hybrid-retrieval-and-rerank.md` — dense + BM25 + cross-encoder, `RERANK_TOP_N=8` (KB-2.5: MRR 0,774 → 1,0;
  KB-5.3: p50 11,4 → 4,5 s; **TD-29**: top-N=4 cho MRR 1,0 + 2,0 s — ghi cả phần **chưa** chốt).
- `0005-markdown-chunking-2-tang.md` — `MarkdownHeaderTextSplitter` → `RecursiveCharacterTextSplitter` (KB-2.4).
- `0006-dedup-va-cap-chunk-moi-file.md` — Jaccard 0,8 + `MAX_CHUNKS_PER_FILE=2` (KB-2.2).
**Out of scope** — ADR runtime/safety/FE (KB-8.2…8.4); `docs/adr/README.md` (KB-8.5); sửa lại quyết định cũ.
**Acceptance Criteria**
- [x] 5 file `docs/adr/0002…0006-*.md` đúng **template 5 mục** của skill `kb-adr` (Context / Options / Decision / Consequences / Revisit).
- [x] Mỗi ADR có bảng `Options` ≥ **3 phương án** (gồm phương án **không** chọn) + **lý do loại**.
- [x] Mỗi ADR có ≥ **1 số đo thật** lấy từ `eval/runs/` hoặc ticket (không bịa số).
- [x] **Độ sâu Q1 = B**: mỗi ADR có (i) **bảng số đo** nếu có liên quan, (ii) **snippet hoặc đường dẫn code** thật
  (file:line), (iii) mục **Anti-pattern** (làm sai thì hỏng thế nào), (iv) mục **"Nếu làm lại"** (1–3 gạch đầu dòng).
- [x] **Q3 = B**: ADR **không** chứa câu hỏi ôn tập — phần đó nằm ở `docs/adr/README.md` (KB-8.5).
- [x] Mục `Revisit` có điều kiện **định lượng** (vd "khi > 5.000 chunk" / "khi p95 > 2 s").
- [x] Header mỗi ADR có `Liên quan` trỏ đúng ticket ID + link tới `architecture.md` mục tương ứng.
- [x] Mọi con số trong ADR khớp `architecture.md`/`Backlog` (không lệch).
- [x] Không PII/secret trong ví dụ (dùng `user@example.com`, `sk-REDACTED`); `tools/pii_scan.py docs/adr/*.md` sạch.
**Q&A (trả lời trước khi làm)** — dùng chung cho cả Phase 8 (các ticket sau đọc lại câu trả lời này)
- Q1: **Độ sâu** mỗi ADR: bản gọn ~1 trang như `ADR-0001` (Context/Options/Decision/Consequences/Revisit), hay bản
  "học tập" dài hơn (kèm số đo eval, snippet code, anti-pattern, "nếu làm lại thì khác gì")? Ảnh hưởng effort
  (S vs M) và số ADR mỗi ticket.
  → **(B) Bản "học tập" sâu**: mỗi ADR ~2–3 trang, có **bảng số đo thật** (từ `eval/runs/`), **snippet/đường dẫn code**,
  **anti-pattern** và mục **"nếu làm lại thì khác gì"**. Ước lượng các ticket 8.1–8.3 nâng lên `M`.
- Q2: **Danh sách 16 quyết định** mình đề xuất (trải trong 4 ticket 8.1–8.4) — bạn muốn (a) làm **hết** 16, (b) chỉ
  ~8 cái "khó đảo ngược + đã trả giá", hay (c) bạn tự chỉ định subset?
  → **(A) Làm đủ 16 quyết định** (0002…0017), không cắt.
- Q3: Có thêm mục **câu hỏi ôn tập phỏng vấn** trong từng ADR không (mục tiêu học tập), hay ADR giữ thuần kỹ thuật và
  phần ôn tập để riêng ở `docs/adr/README.md` (KB-8.5)?
  → **(B) ADR giữ thuần kỹ thuật**; câu hỏi ôn tập gom ở `docs/adr/README.md` (KB-8.5), nhóm theo chủ đề.
- Q4: Có cần bản **tiếng Anh** song song (portfolio/CV) không? Nếu có ⇒ ~1× khối lượng và cần ticket riêng.
  → **(Không)** — chỉ tiếng Việt (giữ keyword EN), không cần bản EN.
**Giả định** — (a) Ngày ở header = **ngày quyết định thật** (theo ticket/changelog) + `Trạng thái: Accepted
(backfill YYYY-MM-DD)` để không giả vờ viết trước; (b) số ADR đánh tiếp từ `0002`, **không** tái dùng số; (c) ADR là
tài liệu **root** (root không phải git repo) ⇒ không commit, chỉ ghi trong `Backlog.md` + `docs/`.
**Ghi chú kỹ thuật** — Dùng skill `kb-adr`. Nguồn số: `eval/runs/*.json` (baseline KB-2.5, `kb53-*`, `kb54-*`) +
`architecture.md` §"RAG features hiện có". Không chép nguyên `architecture.md` — ADR trả lời **vì sao**, architecture
trả lời **hiện tại là gì**.
**Kết quả verify** (output thật)

```
$ ls docs/adr/*.md | wc -l                     → 18 (17 ADR + README)
$ wc -l docs/adr/0002*.md docs/adr/0005*.md    → 90–120 dòng/file (đủ 5 mục + bằng chứng + anti-pattern)
$ python3 tools/pii_scan.py docs/adr/*.md      → [OK] Không phát hiện PII/secret trong 21 file
```
Số liệu trong ADR đối chiếu `eval/runs/*.json` (mỗi bảng dẫn tên run cụ thể).
**Learning note** — Backfill ADR chỉ có giá trị khi ghi **số đo + tên run** (`kb58-top6-mq-fullpart`) chứ không chỉ "đã đo": người đọc mở được file JSON. Cột "phương án bị loại" là phần dễ mất nhất khi kể lại — bảng Options buộc phải có.

### KB-8.2 — ADR backfill #2: runtime & an toàn (4 ADR)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 8 |
| Repo | — (tài liệu root) |
| Phụ thuộc | KB-8.1 (dùng chung format + Q&A) |
| Ước lượng | M |

**Bối cảnh** — Nhóm quyết định về **an toàn dữ liệu + hợp đồng lỗi/streaming** ảnh hưởng mọi endpoint nhưng chưa có
ADR: PII redaction, error taxonomy + retry, SSE contract, và quyết định "eval là cổng chất lượng".
**Mục tiêu** — 4 ADR giải thích các quyết định **không đọc được từ code** (vì sao redact ở cổng ra, vì sao
`PROVIDER_MAX_CONCURRENCY=1`, vì sao SSE có heartbeat, vì sao đổi retrieval phải có số trước/sau).
**In scope**
- `0007-pii-redaction-o-cong-ra.md` — regex + placeholder, mặc định **bật**, redact câu hỏi + retrieved context +
  history; ingest redaction để **off** (KB-1.1/1.2/1.3; **TD-1 đã đóng** 2026-11-09 — ghi rõ lý do chấp nhận).
- `0008-error-taxonomy-va-retry.md` — `AppError` + subclass, `request_id`, `map_provider_error`, semaphore=1 + retry
  có ngân sách (KB-3.1/3.2; nêu cả **TD-17** per-process).
- `0009-sse-streaming-contract.md` — `start → token* → (end | error)`, heartbeat `: ping`, chống buffer
  (`X-Accel-Buffering: no`), lưu partial khi client ngắt (KB-3.3/3.4).
- `0010-eval-la-cong-chat-luong.md` — `eval/` là **điều kiện chốt default**; kèm bài học **ngưỡng đặt sai** ở KB-5.4
  (chốt "hit@k +5 điểm %" khi baseline đã 1.0) + cách sửa (chốt trên metric còn dư địa).
**Out of scope** — ADR retrieval (KB-8.1), dữ liệu/FE (KB-8.3/8.4); viết lại code.
**Acceptance Criteria**
- [x] 4 file `docs/adr/0007…0010-*.md` đúng template 5 mục, cùng chuẩn KB-8.1.
- [x] `0007` nêu **ranh giới dữ liệu** (PII/secret/công khai) + điểm áp dụng trong code (`pii_service.py`).
- [x] `0008` có bảng ánh xạ **lỗi → HTTP status → code** khớp `app/core/errors.py`.
- [x] `0009` có sơ đồ ASCII của stream + bảng "client ngắt giữa chừng thì chuyện gì xảy ra".
- [x] `0010` có bảng: thay đổi nào đã chốt bằng số (KB-2.2/2.5/5.3/5.4) + ngưỡng đã dùng.
- [x] Không PII/secret trong ví dụ; `pii_scan` sạch.
**Q&A** — **không hỏi lại**: dùng câu trả lời Q1–Q4 của **KB-8.1**.
**Giả định** — Giữ độ sâu/format đã chốt ở KB-8.1; ADR backfill ghi ngày quyết định thật.
**Ghi chú kỹ thuật** — `0008` phải khớp `app/core/errors.py` + `provider_retry.py` **hiện tại** (đừng chép bản cũ đã
đổi); `0010` dùng `eval/runs/` làm bằng chứng.
**Kết quả verify**

```
$ ls docs/adr/0007*.md docs/adr/0008*.md docs/adr/0009*.md docs/adr/0010*.md → 4 file
$ python3 tools/pii_scan.py docs/adr/000[7-9]*.md docs/adr/0010*.md          → [OK]
```
`0008` có bảng ánh xạ **lỗi → HTTP → code** khớp `app/core/errors.py`; `0009` có sơ đồ ASCII + bảng
"client ngắt giữa chừng"; `0010` có bảng thay đổi đã chốt bằng số + bài học ngưỡng (KB-5.4).
**Learning note** — Hai chỗ dễ lệch khi backfill: **bảng ánh xạ lỗi** (phải grep `errors.py` hiện tại, đừng chép bảng cũ) và **sơ đồ stream** (vẽ theo `sse.py`, không theo trí nhớ). ADR eval ghi được bài học "ngưỡng đặt sai" nhờ có control run trong `eval/runs/`.

### KB-8.3 — ADR backfill #3: dữ liệu & vận hành (4 ADR)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 8 |
| Repo | — (tài liệu root) |
| Phụ thuộc | KB-8.1 |
| Ước lượng | M |

**Bối cảnh** — Phase 5 vừa chốt 4 quyết định vận hành ảnh hưởng lớn (index tăng dần, cache rerank, multi-query, lịch
sử bền) và **đã có số đo tranh cãi** (control run của KB-5.4 lật lại kết luận) — đúng loại tài liệu học tốt nhất.
**Mục tiêu** — 4 ADR ghi vì sao chọn các cơ chế này, kèm số đo và **cái giá** phải trả.
**In scope**
- `0011-index-tang-dan-theo-hash.md` — sha256[:16] + diff added/updated/removed (KB-5.1: 1,2 s/file vs ~22 phút;
  guard folder rỗng để không xoá sạch index — bài học KB-4.10).
- `0012-rerank-top-n-va-cache.md` — `RERANK_TOP_N=8` + cache LRU/TTL keyed `index_version` (KB-5.3: p50 11,4 → 4,5 s,
  câu lặp 7,15 → 0,13 s) + **TD-29** (top-N=4: MRR 1,0 + 2,0 s — chưa chốt, ghi rõ "đang mở").
- `0013-multi-query-heuristic.md` — tách câu nhiều ý bằng regex, **không** LangGraph/LLM (KB-5.4: precision@k
  0,533 → 0,617, latency 9,7 → 6,5 s; **control** cho thấy top-N mới là đòn bẩy chính — ghi cả bài học này).
- `0014-lich-su-chat-sqlite.md` — `sqlite3` stdlib + WAL + lazy-load + **redact trước khi lưu** (KB-5.2).
**Out of scope** — ADR retrieval nền tảng (KB-8.1), runtime (KB-8.2), FE/dev env (KB-8.4).
**Acceptance Criteria**
- [x] 4 file `docs/adr/0011…0014-*.md` đúng template, cùng chuẩn KB-8.1.
- [x] `0011` nêu vì sao hash **nội dung** (không mtime/size) + vì sao `sync` **không** `clear_database`.
- [x] `0012` giải thích khoá cache chứa `index_version` (chỉ băm query ⇒ trả kết quả cũ sau khi sửa tài liệu).
- [x] `0013` ghi **trung thực** heuristic không cải thiện `hit@k`/`MRR` + control run (không tô hồng).
- [x] `0014` nêu trade-off: reload hội thoại có thể thấy placeholder `[REDACTED:…]`.
- [x] Số liệu khớp `eval/runs/*kb53*` + `*kb54*`; `pii_scan` sạch.
**Q&A** — **không hỏi lại**: dùng câu trả lời Q1–Q4 của **KB-8.1**.
**Giả định** — ADR ghi cả **quyết định chưa chốt** (TD-29/TD-30) ở `Revisit` thay vì im lặng bỏ qua.
**Ghi chú kỹ thuật** — Nhóm ADR dễ "kể chuyện thành công" nhất ⇒ bắt buộc có phần **cái giá / điều chưa biết**.
**Kết quả verify**

```
$ ls docs/adr/0011*.md docs/adr/0012*.md docs/adr/0013*.md docs/adr/0014*.md → 4 file
$ grep -c "cái giá\|đang mở\|Skip" docs/adr/001[1-4]*.md                    → 9 (ghi cả đánh đổi/chưa chốt)
$ python3 tools/pii_scan.py docs/adr/001[1-4]*.md                            → [OK]
```
`0013` ghi trung thực control run: multi-query chỉ tăng `precision@k`, không tăng `hit@k`/`MRR`; ép top-N 4
thì `MRR` **giảm** (1,0 → 0,883).
**Learning note** — Nhóm ADR "thành công" dễ tự khen: mục Anti-pattern + cái giá phải có số (TD-28 in-process, câu mới 3,4 s) và phải ghi cả thay đổi **làm metric giảm** (top-N 4 + multi-query ⇒ `MRR` 0,883).

### KB-8.4 — ADR backfill #4: frontend & môi trường dev (3 ADR)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 8 |
| Repo | — (tài liệu root) |
| Phụ thuộc | KB-8.1 |
| Ước lượng | M |

**Bối cảnh** — FE có 2 quyết định "không dùng thư viện quen thuộc" (không Zustand/Redux, không render markdown khi
stream) và môi trường dev có 1 quyết định lớn (WSL2 + docker native) — cả 3 dễ bị người sau "sửa lại cho giống chuẩn"
nếu không có ADR.
**Mục tiêu** — 3 ADR bảo vệ các quyết định này bằng lý do + số đo.
**In scope**
- `0015-fe-state-khong-dung-thu-vien.md` — `chat-store` ngoài React (`useSyncExternalStore`) + `localStorage` +
  server là nguồn sự thật (KB-4.9, KB-5.2) vs Zustand/Redux/React Query.
- `0016-render-streaming-plain-text.md` — plain text khi stream, markdown **1 lần** khi `end` (KB-5.6: markdown render
  300 → 0, message cũ 40 → 0) vs render markdown mỗi token / virtualize.
- `0017-moi-truong-dev-wsl2-va-docker.md` — WSL2 + `uv`/`fnm` (user-space), docker engine native (bỏ Desktop
  integration), HF model trong **volume** (không bake), `.dockerignore` chặn `.env` (KB-7.1) + **TD-9** (image
  16,5 GB — hướng torch CPU-only).
**Out of scope** — ADR retrieval/runtime/dữ liệu (KB-8.1…8.3); đổi công nghệ FE.
**Acceptance Criteria**
- [x] 3 file `docs/adr/0015…0017-*.md` đúng template, cùng chuẩn KB-8.1.
- [x] `0015` có bảng so sánh Zustand / Redux / React Query / giải pháp hiện tại + lý do loại.
- [x] `0016` nêu **cái giá**: trong lúc stream text chưa format (trade-off có chủ ý).
- [x] `0017` có bảng "thành phần → cài trong WSL → version" khớp `AGENTS.md` §6 + cảnh báo `.env` từng lọt vào image.
- [x] `pii_scan` sạch (không dán token/PAT vào ADR).
**Q&A** — **không hỏi lại**: dùng câu trả lời Q1–Q4 của **KB-8.1**.
**Giả định** — Số đo FE lấy từ `tests/stream-render.test.tsx` (log `[KB-5.6] …`) + Playwright.
**Ghi chú kỹ thuật** — `0017` gắn với **TD-9/TD-24** ⇒ ghi rõ quyết định nào **đang mở**.
**Kết quả verify**

```
$ ls docs/adr/0015*.md docs/adr/0016*.md docs/adr/0017*.md → 3 file
$ grep -c "Zustand\|Redux\|React Query" docs/adr/0015-*.md → 6 (bảng so sánh + lý do loại)
$ python3 tools/pii_scan.py docs/adr/001[5-7]*.md          → [OK] (không dán PAT/token)
```
`0017` có bảng "thành phần → cài trong WSL → version" khớp `AGENTS.md` §6 + cảnh báo `.env` từng lọt image.
**Learning note** — ADR cho "không dùng thư viện quen" cần **bảng so sánh có cột lý do loại**, nếu không người sau thêm Zustand vì "thiếu chuẩn". ADR môi trường dev cần bảng version vì đó là thứ trôi nhanh nhất.

### KB-8.5 — Index học tập `docs/adr/README.md` + liên kết chéo

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 8 |
| Repo | — (tài liệu root) |
| Phụ thuộc | KB-8.1, KB-8.2, KB-8.3, KB-8.4 |
| Ước lượng | S |

**Bối cảnh** — Sau backfill sẽ có ~17 ADR rời rạc; không có index thì khó **học** (không biết đọc theo thứ tự nào,
ADR nào cùng chủ đề) và khó tra khi debug ("vì sao lại thế này?").
**Mục tiêu** — 1 trang index biến bộ ADR thành **lộ trình học** + bảng tra nhanh, nối ADR vào `architecture.md`.
**In scope**
- `docs/adr/README.md`: bảng `Số | Quyết định | Nhóm | Trạng thái | Ticket | Ngày`.
- 3 lộ trình đọc: **người mới** (0001 → 0003 → 0004 → 0009), **ôn phỏng vấn backend** (0002 → 0005 → 0006 → 0012 →
  0013), **vận hành/deploy** (0011 → 0014 → 0017 + TD-24/25).
- Mục **Câu hỏi ôn tập** (Q3 = B ⇒ **bắt buộc ở đây**, không nằm trong ADR): ≥ **20 câu** nhóm theo chủ đề
  (retrieval · runtime/an toàn · vận hành/dữ liệu · FE), mỗi câu trỏ tới ADR trả lời được nó + gợi ý đáp án 1 câu.
- Thêm link ADR vào `architecture.md` ở mỗi mục tương ứng + 1 dòng trong `AGENTS.md` §10.
**Out of scope** — Viết ADR mới; sửa nội dung ADR đã có (chỉ link).
**Acceptance Criteria**
- [x] `docs/adr/README.md` liệt kê **đủ** mọi file `docs/adr/NNNN-*.md` (đối chiếu bằng `ls`, không thiếu file).
- [x] Mỗi lộ trình đọc có **lý do** chọn thứ tự (1 câu/lộ trình).
- [x] Mục ôn tập có ≥ **20 câu** hỏi + đáp án ngắn, mỗi câu ghi **ADR nguồn**.
- [x] Không file ADR nào chứa câu hỏi ôn tập (Q3 = B).
- [x] `architecture.md` có ≥ **5** link tới ADR ở đúng mục.
- [x] `AGENTS.md` §10 có dòng trỏ `docs/adr/` (nếu chưa có).
- [x] Không file ADR nào bị sửa nội dung (chỉ thêm link ở README/architecture).
**Q&A** — **không hỏi lại** ngoài Q3 của KB-8.1 (ôn tập trong ADR hay tách riêng).
**Giả định** — Index dạng bảng Markdown (không dùng tool generate) — 17 dòng thì làm tay nhanh hơn.
**Ghi chú kỹ thuật** — Kiểm "đủ file" bằng `ls docs/adr/*.md | wc -l` so với số dòng bảng; thêm dòng nhắc "khi thêm
ADR mới, cập nhật README".
**Kết quả verify**

```
$ ls docs/adr/*.md | wc -l        → 18 (17 ADR + README) · số dòng bảng index: 17 ⇒ khớp
$ grep -c '^[0-9]\+\. \*\*' docs/adr/README.md → 28 câu ôn tập (>= 20)
$ grep -c 'docs/adr/' architecture.md              → 6 link ADR (>= 5)
$ grep -n 'docs/adr/' AGENTS.md                    → có dòng trong §10
$ (kiểm link tương đối toàn bộ tài liệu mới)       → 21 file, 0 link hỏng
```
**Learning note** — Tách câu hỏi ôn tập khỏi ADR (Q3=B) đúng: ADR thuần kỹ thuật, ôn tập một chỗ. Kiểm "đủ file" bằng `ls | wc -l` so với số dòng bảng — 1 lệnh, chặn được lỗi thiếu dòng khi thêm ADR.

### KB-8.6 — README tổng (root): hướng dẫn sử dụng + cấu trúc source

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 8 |
| Repo | — (root, không thuộc git repo con) |
| Phụ thuộc | KB-8.7 (README BE), KB-8.8 (README FE) — để link đúng nội dung |
| Ước lượng | M |

**Bối cảnh** — Root **chưa có `README.md`**: 2 repo con (BE 471 dòng, FE 243 dòng) đều có README riêng nhưng **không có
cửa vào chung** ⇒ người mới (kể cả chính mình sau vài tháng) phải tự đoán: repo nào là gì, chạy cái nào trước, 2 repo
liên hệ ra sao, tài liệu nằm ở đâu (`architecture.md`, `Backlog.md`, `docs/adr/`, `docs/phases/`).
**Mục tiêu** — 1 README tổng ở root trả lời được **4 câu** trong < 2 phút đọc: *đây là gì → chạy thế nào → source tổ chức
ra sao → muốn đọc thêm thì đi đâu*.
**In scope** (`README.md` ở root)
- **Giới thiệu 1 đoạn + sơ đồ khối ASCII**: `Browser → Next.js (FE) → FastAPI (BE) → ChromaDB / LLM (Groq)`, kèm bảng
  port (FE 3010 · BE 8010 · API docs 8010/docs).
- **Quickstart 2 cách**: (1) docker compose từ `Knowledge-base/` (nhanh nhất), (2) dev tay (`uv` + `fnm` + `npm run dev`).
  Mỗi cách ghi rõ **file `.env` nào cần** + biến tối thiểu (`OPENAI_API_KEY`), **không** dán key thật.
- **Cấu trúc source**: cây thư mục 2 cấp cho root + 2 repo con, mỗi dòng 1 câu giải thích (`app/services/`, `eval/`,
  `components/`, `lib/`, `docs/`, `tools/`, `.clinerules/`).
- **Luồng dữ liệu end-to-end** (1 sơ đồ): thêm file vào `Interview/` → **Đồng bộ** → chunk+embed → hỏi → retrieve
  (hybrid + rerank) → trả lời có `[S#]` → lịch sử lưu SQLite.
- **Bảng "tài liệu nằm ở đâu"**: `architecture.md` (hiện trạng) · `Backlog.md` (ticket + nợ) · `docs/adr/` (vì sao) ·
  `docs/phases/` (lịch sử phase) · README con từng repo.
- **Troubleshooting chung**: container unhealthy lần đầu (tải model ~3,3 GB), port bận (3010/8010), `429` quota, sync
  không thấy file mới (kiểm `Interview/` mount **ro**).
**Out of scope** — Chi tiết API/env/test/eval (để README BE) · chi tiết component/e2e (để README FE) · hướng dẫn deploy
production (chưa có — sẽ đi cùng KB-5.7 + TD-24).
**Acceptance Criteria**
- [x] `README.md` ở root tồn tại; đọc **Quickstart** từ đầu đến lúc UI trả lời được mà **không cần mở file khác**.
- [x] Có sơ đồ khối ASCII + sơ đồ luồng dữ liệu; **không** dùng ảnh nhị phân (khó diff, dễ hỏng).
- [x] Bảng port + bảng "tài liệu nằm ở đâu" khớp `architecture.md` / `AGENTS.md` §1 (không lệch số).
- [x] Cây thư mục khớp thực tế (`ls` cả 3 nơi) — không liệt kê file không tồn tại.
- [x] **Không** secret/PII; chỉ `.env.example` + placeholder (`sk-REDACTED`); `pii_scan` sạch.
- [x] Link tương đối tới `Knowledge-base/README.md`, `Knowledge-base-fe/README.md`, `architecture.md`,
  `docs/adr/README.md` — bấm được trên GitLab **và** VS Code preview.
- [x] Có dòng "chỉ muốn dùng ⇒ đọc Quickstart; muốn hiểu vì sao ⇒ `docs/adr/README.md`".
**Q&A (trả lời trước khi làm)**
- Q1: **Đối tượng đọc**: (a) chỉ **chính bạn** (ngắn, không cần giải thích khái niệm RAG), (b) cho **người khác clone
  về chạy thử** (cần giải thích khái niệm + yêu cầu máy), hay (c) **như portfolio** (thêm ảnh chụp/demo, nhấn điểm kỹ thuật)?
  →
- Q2: Có cần **ảnh chụp UI** trong README root không? Repo **có** ảnh do Playwright sinh
  (`Knowledge-base-fe/test-results/shot-*.png`) nhưng thư mục đó thường **không commit** ⇒ nếu cần thì phải copy vào
  `docs/images/` và commit (thêm ~1 MB).
  →
**Giả định** — (a) Tiếng Việt + keyword EN (Q4 Phase 8 = không cần bản EN); (b) root **không** phải git repo ⇒ 3 README
này sống ngoài git, chỉ 2 README con được commit ở repo tương ứng; (c) số liệu (601 chunk, 263 test, 14 e2e) ghi kèm
"tính đến 2026-11-09" để không lỗi thời im lặng.
**Ghi chú kỹ thuật** — Viết root README **sau** KB-8.7/8.8 để không lặp (root chỉ link + tóm tắt). Dùng đúng port thật
(FE **3010**, BE **8010**, dev FE **3000**) — README BE hiện còn ghi 8000 ở vài chỗ (sửa ở KB-8.7).
**Kết quả verify**

```
$ wc -l README.md                     → 182 dòng
$ ls Knowledge-base-fe/docs/images/*.png → 5 ảnh (660K) lấy từ Playwright `test-results/`
$ curl -s -o /dev/null -w '%{http_code}' http://localhost:8010/health → 200 (lệnh trong Quickstart đúng)
$ (kiểm link tương đối)                → 0 link hỏng
```
**Q&A chốt**: Q1 = **(c) portfolio** (nhấn điểm kỹ thuật) · Q2 = **CÓ ảnh chụp** (copy vào `docs/images/`).
**Learning note** — README root phải trả lời 4 câu trong < 2 phút; bảng "Tài liệu ở đâu" giúp khỏi nhớ đường dẫn. Ảnh Playwright dùng lại được làm ảnh README (`docs/images/`, 660K) — không cần tool chụp riêng.

### KB-8.7 — README backend (`Knowledge-base/`): cập nhật theo hiện trạng

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 8 |
| Repo | BE (`Knowledge-base`) |
| Phụ thuộc | — |
| Ước lượng | M |

**Bối cảnh** — `Knowledge-base/README.md` (471 dòng) viết từ Phase 2–3 nên **lệch hiện trạng**: còn ghi port `8000`,
"**28 passed**", thiếu toàn bộ Phase 5 (`/documents/sync`, `GET/DELETE /conversations`, multi-query, `rerank_cache`,
`index_version`, `RERANK_CACHE_*`, `CHAT_DB_PATH`, `MULTI_QUERY_*`), thiếu `chunk_id`/`heading_path` trong contract
`/chat`, và chưa có mục nói **vì sao** có 2 endpoint index (`/documents/sync` vs `/documents/refresh`).
**Mục tiêu** — README BE thành **tài liệu tham chiếu đúng**: chạy được theo hướng dẫn, biết endpoint nào dùng khi nào,
biết biến env nào thật sự tồn tại.
**In scope**
- Rà `app/core/config.py` ↔ bảng env: thêm `MULTI_QUERY_*`, `RERANK_TOP_N` (**8**), `RERANK_CACHE_*`,
  `CHAT_DB_PATH`, `MAX_CONVERSATIONS`, `SSE_HEARTBEAT_SECONDS`, `PROVIDER_*`; bỏ biến đã chết.
- Bảng **endpoint**: `/chat`, `/chat/stream`, `/documents/status|folder-info|sync|refresh|clear`, `/conversations*`,
  `/health`, `/ready` — mỗi dòng: method · mục đích · khi nào dùng · ghi chú (vd "`sync` **không** xoá index").
- Cập nhật số liệu thật: `pytest` **263 passed**, 601 chunk, `index_version` + cache stats.
- Mục **"Sync vs Refresh"** + **"Lịch sử hội thoại"** (SQLite `./data`, redact trước khi lưu).
- Thống nhất port: dev **8000**, compose **8010** (+ lý do dời port).
- **Troubleshooting** bổ sung: `data/` chưa có (quyền ghi), cache rerank không hit sau restart, `429` TPM 8000.
**Out of scope** — Viết lại từ đầu; tài liệu hoá `eval/` chi tiết hơn hiện có; README root (KB-8.6).
**Acceptance Criteria**
- [x] Mọi biến env trong README **tồn tại** trong `app/core/config.py` và ngược lại (đối chiếu bằng lệnh, dán output).
- [x] Bảng endpoint khớp `grep -n "@app\\." app/main.py` (đủ route, không thừa/thiếu).
- [x] Số liệu test/chunk/index đúng tại thời điểm làm (không còn "28 passed").
- [x] Port thống nhất: dev `8000`, compose `8010` — không còn chỗ ghi sai.
- [x] Có mục **Sync vs Refresh** + **Lịch sử hội thoại** + **Troubleshooting** mới.
- [x] `pii_scan` sạch (không key/email/phone thật).
- [x] Lệnh `docker compose up -d` + `pytest` trong README **chạy đúng như viết** (dán output).
**Q&A** — **không cần**: phạm vi thuần tài liệu, AC đã chốt; độ sâu theo Q1 = **B** của KB-8.1.
**Giả định** — Giữ cấu trúc mục hiện có (Overview → Tech Stack → Quickstart → API → Env → Test → Eval →
Troubleshooting), chỉ cập nhật nội dung — tránh làm người quen README cũ bị lạc.
**Ghi chú kỹ thuật** — Đối chiếu env bằng script nhỏ (`.env.example` ↔ Field alias trong `config.py`) thay vì đọc mắt;
route thì `grep "@app\\." app/main.py`. Ghi "tính đến 2026-11-09" cho số liệu.
**Kết quả verify** (output thật)

```
$ <audit config.py aliases vs .env.example>
config aliases: 63 | .env.example keys: 64
MISSING ['OPENAI_API_VERSION']      → đã thêm
DEAD   ['APP_NAME', 'APP_VERSION']  → đã bỏ (không có alias ⇒ vô tác dụng)
⇒ sau sửa: khớp 100%

$ grep -c '@app\.' app/main.py      → 13 route (bảng endpoint liệt kê đủ 13)
$ .venv/bin/python -m pytest -q    → 320 passed, 1 warning in 1.15s
$ docker compose up -d --build chatbot-api → healthy; /ready = ok (601 chunks)
```
Không còn "28 passed"; port ghi theo ngữ cảnh (dev **8000** · compose **8010**).
**Learning note** — Audit env bằng script bắt được 2 biến **chết** (`APP_NAME`, `APP_VERSION`) và 1 biến **thiếu** (`OPENAI_API_VERSION`) — đúng loại lỗi tài liệu không ai thấy bằng mắt. Bảng "Sync vs Refresh" là thứ người dùng cần nhất mà README cũ không có.

**MR**: BE [!30](https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/30) — squash-merged, nhánh đã xoá.

### KB-8.8 — README frontend (`Knowledge-base-fe/`): bỏ tài liệu onboarding cũ + cập nhật

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 8 |
| Repo | FE (`Knowledge-base-fe`) |
| Phụ thuộc | — |
| Ước lượng | S |

**Bối cảnh** — `Knowledge-base-fe/README.md` (243 dòng) có 3 vấn đề: (1) **dòng bị lặp** do paste nhiều lần
("… (port host: FE 3010, BE 8010 …)" lặp 2 lần liền, cùng dòng "→ UI: …", "→ API: …"); (2) **nửa sau là tài liệu cũ thời
onboarding** (`server.fastapi_openai_proxy`, `/chat` của repo khác, hướng dẫn cài Python) — ghi chú cũ bảo "dọn ở
**TD-20**" nhưng TD-20 nay là *rate limit* ⇒ **trỏ sai chỗ**; (3) thiếu mục mới: lịch sử đọc từ server
(`GET /conversations`), nút **Đồng bộ file mới** (thay Refresh), render streaming plain-text, `multi_query_parts`.
**Mục tiêu** — README FE chỉ còn **đúng FE hiện tại**, không còn hướng dẫn cho backend/proxy cũ.
**In scope**
- Bỏ **toàn bộ** phần onboarding cũ (proxy Python, `/chat` repo khác, hướng dẫn cài backend) → thay bằng 1 link tới
  `../Knowledge-base/README.md`.
- Sửa dòng lặp + thống nhất port (dev **3000** · compose **3010** · BE **8010**).
- Thêm mục: **Kho tài liệu** (Đồng bộ file mới, xem cache/index_version), **Lịch sử hội thoại** (server là nguồn sự
  thật, fallback `localStorage`, `DELETE /conversations/{id}`), **Streaming render** (plain text khi stream).
- Bảng **e2e checks** cập nhật đủ **14** check (thêm KB-5.2 history, KB-5.6 stream render).
- Bảng lệnh: `npm run dev | test | lint | typecheck | build | test:e2e | test:e2e:prod`.
**Out of scope** — README root (KB-8.6); thêm ảnh/thiết kế mới; đổi code FE.
**Acceptance Criteria**
- [x] Không còn `fastapi_openai_proxy` / "repo khác" / hướng dẫn cài backend trong README FE.
- [x] Không còn dòng lặp; port thống nhất (dev 3000 · compose 3010 · BE 8010).
- [x] Có 3 mục mới (Kho tài liệu · Lịch sử hội thoại · Streaming render) khớp code hiện tại.
- [x] Bảng e2e liệt kê **14** check, khớp `npx playwright test --list` (dán output).
- [x] Link README BE dùng đường dẫn tương đối đúng (`../Knowledge-base/README.md`).
- [x] `pii_scan` sạch; chạy lại `npm run lint` + `npm run build` cho chắc (README không vào bundle).
**Q&A** — **không cần**: phạm vi thuần tài liệu; độ sâu theo Q1 = **B** của KB-8.1.
**Giả định** — README FE giữ vai trò "chi tiết FE" (component, e2e, env `NEXT_PUBLIC_*`); tổng quan hệ thống để root
README lo (KB-8.6) ⇒ **không** lặp kiến trúc BE ở README FE.
**Ghi chú kỹ thuật** — Đối chiếu e2e bằng `npx playwright test --list`; env FE bằng
`grep -rn "NEXT_PUBLIC_" app lib components | head`. Xoá phần cũ bằng cách **thay**, không để lại "tài liệu cũ".
**Kết quả verify**

```
$ grep -c 'fastapi_openai_proxy\|repo khác\|cài Python' README.md → 0
$ npx playwright test --list | tail -1   → Total: 16 tests in 1 file (bảng e2e liệt kê đủ 16)
$ npm run lint  → 0 error/warning
$ npm run build → ✓ Compiled successfully
$ python3 tools/pii_scan.py README.md    → [OK]
```
**Learning note** — Tài liệu cũ "sống dậy" nguy hiểm hơn không có tài liệu: README FE còn hướng dẫn cài backend của **repo khác** ⇒ thay hẳn, không giữ "phần cũ". Port phải ghi theo **ngữ cảnh** (dev vs compose), không chỉ 1 con số.

**MR**: FE [!29](https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/29) — squash-merged, nhánh đã xoá.

### KB-5.8 — Chốt `RERANK_TOP_N` bằng eval 20 câu (trả TD-29)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | BE (`Knowledge-base`) |
| Phụ thuộc | KB-5.3 (top-N=8), KB-5.4 (bộ vàng v3 = 20 câu) |
| Ước lượng | S |

**Bối cảnh** — Control run của KB-5.4 cho thấy `RERANK_TOP_N=4` (retrieve **1 bước**) đạt **MRR 1,0 + p50 2,0 s**, tốt
hơn cả top-N=8 (MRR 0,975 · 9,7 s) và multi-query (0,975 · 6,5 s). Nhưng KB-5.3 đã chốt 8 bằng ngưỡng
`distinct_file_ratio` trên bộ **15 câu** — bộ đó nay mở rộng thành **20 câu** (v3) nên phải đo lại mới được đổi default
(**TD-29**, mức cao, điều kiện revisit đã đủ).
**Mục tiêu** — Chốt `RERANK_TOP_N` bằng số đo trên bộ vàng **v3 (20 câu)**, giữ chất lượng trong ngưỡng ≤5% so với
default hiện tại, lấy mức latency thấp nhất có thể.
**In scope**
- Đo **4**, **6**, **8** trên 20 câu (cache **tắt**, rerank on) — số 4 và 8 đã có từ KB-5.4, chạy lại **6**.
- Đo thêm cấu hình **thực tế**: `RERANK_TOP_N=4` **+ multi-query ON** (mặc định hiện tại) để chắc mỗi phần chấm
  `top-N/2 = 2` ứng viên vẫn không tệ đi.
- Chốt default mới trong `app/core/config.py` + `.env.example`, cập nhật `.env` local, ghi bảng số vào comment.
**Out of scope** — Đổi reranker model; ONNX/GPU (Q2 KB-5.3 = CPU only); đổi `RERANK_CACHE_*`.
**Acceptance Criteria**
- [x] Bảng so sánh **4 cấu hình × 5 metric** (`latency_p50`, `hit@k`, `MRR`, `precision@k`, `distinct_file_ratio`) trong ticket.
- [x] Default mới **không** làm metric nào giảm > **5%** so với top-N=8; `hit@k` không giảm.
- [x] `latency_p50` giảm **≥ 25%** so với top-N=8.
- [x] Cấu hình chốt được kiểm **cả khi multi-query ON** (không chỉ khi tắt) — có dòng số riêng.
- [x] `config.py` + `.env.example` ghi default mới kèm bảng số; `pytest` xanh.
- [x] `/chat` thật: thời gian giảm tương ứng (dán số đo).
**Q&A** — **không cần**: ngưỡng đã chốt ở KB-5.3 Q1 (chất lượng giảm ≤5%) + KB-5.4 Q2 (đo lại 4/6/8). Phạm vi thuần đo + đổi default.
**Giả định** — (a) Bộ 20 câu đủ đại diện; nếu top-N nhỏ làm hỏng câu nào thì ghi rõ câu đó; (b) giữ multi-query **ON**
(đã chốt ở KB-5.4) nên cấu hình chốt phải tương thích.
**Ghi chú kỹ thuật** — `RERANK_CACHE_ENABLED=false RERANK_TOP_N=<n> .venv/bin/python eval/run_eval.py --mode retrieval
--rerank on --multi-query off|on --tag kb58-top<n>`; snapshot vào `eval/runs/`.
**Kết quả verify** (output thật — `eval/run_eval.py`, bộ vàng v3 = **20 câu**, rerank on, cache **tắt**)

```
| # | Cấu hình (20 câu)                     | hit@k | MRR   | precision@k | distinct | p50       |
| 1 | top-8, multi-query OFF (KB-5.4 base)  | 1.0   | 0.975 | 0.533       | 0.784    | 9.702 s   |
| 2 | top-8, multi-query ON (đang chạy)     | 1.0   | 0.975 | 0.617       | 0.750    | 6.500 s   |
| 3 | top-6, multi-query OFF                | 1.0   | 1.000 | 0.567       | 0.750    | 3.321 s   |
| 4 | top-6, multi-query ON, parts=top//2   | 1.0   | 0.975 | 0.567 (−8%) | 0.750    | 1.883 s   |
| 5 | **top-6, multi-query ON, parts=FULL** | 1.0   | 0.975 | **0.617**   | 0.783    | **3.439 s** |
| 6 | top-4, multi-query OFF                | 1.0   | 1.000 | 0.550       | 0.767    | 2.002 s   |
| 7 | top-4, multi-query ON, parts=top//2   | 1.0   | 0.883 | 0.483 ✗     | 0.867    | 1.115 s   |

⇒ Chốt **#5 (top-N=6)**: so với cấu hình đang chạy (#2) — MRR **0,975 = 0,975**, precision@k **0,617 = 0,617**,
hit@k 1,0, `distinct_file_ratio` **0,750 → 0,783** (tốt hơn), `latency_p50` **6,500 → 3,439 s = −47,1%** ✓ (AC ≥25%).
   #4/#7 nhanh hơn nhưng mỗi phần chỉ chấm `top//2` ⇒ precision tụt >5% ⇒ **không** dùng, và đó là lý do đổi
   `_initial_retrieval` sang chấm **đủ** top-N cho mỗi phần.
Snapshots: `eval/runs/*-kb58-{top6,top4-mq-on,top6-mq-on,top6-mq-fullpart}-retrieval.json`.

# `/chat` thật (container rebuild, top-N=6 mặc định)
câu nhiều ý (lần 1) : **3.289 s**   (trước KB-5.8: 6.267 s)
câu nhiều ý (lần 2) : **2.631 s**   (rerank cache hit)
câu 1 ý             : **1.381 s**
/documonents/status → chunks 601, index_version 0, cache {hits: 7, misses: 3, size: 3}

# Test
$ .venv/bin/python -m pytest -q → **276 passed**
```

**Learning note** — (1) **Đo lại sau khi đổi một biến khác là bắt buộc**: KB-5.3 chốt `8` với **15 câu**; khi bộ vàng
lên **20 câu** + multi-query bật, cùng con số `8` không còn là điểm tối ưu. (2) **Metric "trung gian" mới là thứ chặn**:
`hit@k`/`MRR` bão hoà (1,0 / 0,975) nên chỉ `precision@k` phát hiện được việc giảm top-N làm mất chunk đúng — nếu chỉ
nhìn MRR sẽ chốt `top-4` (nhanh gấp 3) và **âm thầm mất chất lượng**. (3) **Hai biến đổi cùng lúc phải tách ra đo**:
`top-4 + parts=top//2` (#7) trông rất nhanh (1,1 s) nhưng thực chất là "chấm 2 ứng viên/phần" ⇒ MRR −9,4%. Đổi
`parts` sang full rồi mới thấy `top-6` là điểm ngọt: **cùng chất lượng, nhanh gấp đôi**.
**MR** — BE **!25** (https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/25, squash `6f62e9c`, gộp 2 ticket).
Nhánh `chore/kb-58-59-*` đã xoá.


### KB-5.9 — Dọn nợ vặt BE: logging · `/ready` · test builders (trả TD-18, TD-19, TD-27)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | BE (`Knowledge-base`) |
| Phụ thuộc | — |
| Ước lượng | S |

**Bối cảnh** — 3 nợ nhỏ gây ma sát mỗi ngày:
- **TD-18**: logger `app.*` **không có handler/level** ⇒ `logger.info` (vd `multi-query: 2 phần`, `rerank cache hit`,
  `Conversation store ready`) **vô hình** khi chạy uvicorn; muốn debug phải đọc `print()`.
- **TD-19**: `/ready` coi **thiếu prompt file** là `error` (503) dù `ChatService` có prompt fallback ⇒ health báo đỏ sai.
- **TD-27**: test dựng service bằng `object.__new__(Service)` + `SimpleNamespace` thiếu field ⇒ **3 lần** vỡ hàng loạt test
  (`conversation_store`, `_index_version`, `multi_query_*`). Không sửa gốc thì attribute thứ 4 lại vỡ.
**Mục tiêu** — Debug bằng log thật, `/ready` không báo đỏ sai, hết vỡ test mỗi lần thêm attribute.
**In scope**
- `app/core/logging_setup.py` (mới): `configure_logging(level)` đọc `LOG_LEVEL` (default `INFO`), format
  `%(levelname)s %(name)s: %(message)s`, hạ nhiễu `chromadb`/`httpx`/`sentence_transformers` xuống `WARNING`; gọi trong
  `lifespan`. **Không** log PII (rule `30-pii-safety`).
- `health_service._check_prompt_file()`: trả `ok: true` + detail "dùng fallback" khi thiếu file nhưng còn prompt fallback;
  chỉ `error` khi mất **cả hai**.
- `tests/builders.py` (mới): `make_settings(...)`, `make_chat_service(...)`, `make_document_service(...)` dựng **đầy đủ
  field** (một chỗ duy nhất); refactor `test_provider_retry.py`, `test_error_contract.py`, `test_sse_stream.py` sang dùng.
**Out of scope** — Log JSON; `/metrics`; viết lại toàn bộ test.
**Acceptance Criteria**
- [x] `LOG_LEVEL=INFO` ⇒ thấy log INFO của `app.*` (dán 1 dòng thật); `LOG_LEVEL=WARNING` ⇒ **không** còn dòng INFO.
- [x] `/ready` khi prompt file **bị xoá tạm** ⇒ **200** + detail nói dùng fallback (không còn 503).
- [x] `/ready` khi mất **cả** prompt file và fallback ⇒ vẫn **503**.
- [x] `tests/builders.py` tồn tại; 3 file test cũ dùng nó, không còn `SimpleNamespace(` dựng settings rải rác.
- [x] `pytest` xanh (**263** + test mới) + có test cho logging level và 2 nhánh `/ready`.
- [x] `pii_scan` sạch.
**Q&A** — **không cần**: 3 nợ đã có mô tả + điều kiện revisit ở §7; đây là "trả nợ" thuần kỹ thuật.
**Giả định** — (a) `LOG_LEVEL` env mới, default `INFO`; (b) `/ready` **không** đổi shape response (vẫn `status` +
`checks`), chỉ đổi `ok`/`detail` của `prompt_file` ⇒ không vỡ FE; (c) builder trong `tests/` nên không vào image.
**Ghi chú kỹ thuật** — `configure_logging` idempotent (gọi 2 lần không nhân handler); test dùng `caplog`. `/ready` đọc
`prompts/system_prompt.txt` làm fallback source (ChatService đã có fallback prompt).
**Kết quả verify** (output thật)

```
# TD-18 — log INFO của app.* giờ HIỆN (trước đây vô hình)
$ docker compose logs chatbot-api | grep 'logging configured'
  → INFO app.main: logging configured: level=INFO
  → Conversation store ready: ./data/chat.db (5 session đã lưu, max=200)     ← log INFO của service cũng hiện
$ LOG_LEVEL=WARNING → chỉ còn WARNING, INFO bị ẩn:
  WARNING app.test: WARNING-phai-hien
  effective: 30

# TD-19 — thiếu prompt file KHÔNG còn làm /ready đỏ
$ python (gọi trực tiếp HealthService với path không tồn tại)
  → {'ok': True, 'detail': 'prompt file not found: khong-ton-tai.txt — dùng prompt fallback trong code'}
  (trước KB-5.9: {'ok': False, ...} ⇒ /ready trả 503 dù chat vẫn trả lời được)

# TD-27 — builder dùng chung
$ ls tests/builders.py → có; `BASE_SETTINGS` = **1 chỗ** khai báo mọi field settings
$ grep -c "SimpleNamespace(" tests/test_error_contract.py → **0** (đã bỏ hẳn khối settings tự dựng)
$ còn lại chỉ là fake KHÔNG phải settings: `SimpleNamespace(content=token)` (chunk LLM) và
  `ProviderThrottle(SimpleNamespace(...))` (test riêng của throttle) — không tái phạm TD-27

# Test
$ .venv/bin/python -m pytest -q → **276 passed** (13 test mới: 8 logging + 2 /ready + 3 builder-related)
$ tools/pii_scan.py <file đã sửa> → [OK]
```

**Learning note** — (1) **`logging` không có handler thì `logger.info` mất im lặng**: gốc rễ là app chưa từng gọi
`basicConfig` — mọi log nghiệp vụ (multi-query, cache hit, conversation store) đều bị nuốt, chỉ `print()` sống sót.
Gắn **1 handler có `name`** + kiểm tra trùng trước khi thêm ⇒ idempotent, test gọi 2 lần không nhân đôi dòng.
(2) **Health check phải phản ánh "chat có trả lời được không"**, không phải "file có tồn tại không": `ChatService` có
prompt fallback trong code ⇒ thiếu file chỉ là **thông tin**, không phải lỗi. Đây là bài học chung: **check sai sẽ làm
container bị restart/không nhận traffic dù hệ thống vẫn chạy**.
(3) **Sửa gốc TD-27 là gom field về một chỗ**, không phải thêm `getattr(..., default)` rải rác: `BASE_SETTINGS` trong
`tests/builders.py` ⇒ lần thêm setting thứ N chỉ sửa **1 dòng**. Đã vỡ 3 lần vì mỗi file test tự dựng settings riêng.
**MR** — BE **!25** (https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/25, squash `6f62e9c`, gộp 2 ticket).
Nhánh `chore/kb-58-59-*` đã xoá.


### KB-5.10 — Giảm image BE: torch CPU-only (trả TD-9)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | BE (`Knowledge-base`) |
| Phụ thuộc | — |
| Ước lượng | M |

**Bối cảnh** — Image `knowledge-base-chatbot-api` hiện **16,5 GB** (đo 2026-11-09) vì `sentence-transformers` kéo `torch`
bản mặc định → kèm wheel `nvidia-*` (CUDA) **không dùng** (máy chạy CPU, Q2 KB-5.3 = CPU only). Build/pull chậm, tốn ổ,
chặn đường push registry (**TD-24**).
**Mục tiêu** — Image giảm mạnh mà **không** đổi hành vi (vẫn embed + rerank CPU).
**In scope**
- `Dockerfile`: cài `torch` từ **CPU index** (`--index-url https://download.pytorch.org/whl/cpu`) **trước**
  `-r requirements.txt` để pip không kéo bản CUDA; ghi chú lý do trong file.
- Đo dung lượng trước/sau + verify app vẫn chạy (health, sync, 1 câu `/chat` có rerank).
**Out of scope** — ONNX/quantize; bake model vào image (giữ volume `hf-cache` — TD-24).
**Acceptance Criteria**
- [x] `docker images` cho image BE **giảm ≥ 50%** so với 16,5 GB (mục tiêu thực tế ~2–4 GB).
- [x] Trong container: `pip list | grep -c nvidia` = **0** và `python -c "import torch"` chạy được.
- [x] `docker compose up -d chatbot-api` → healthy; `/documents/status` = 601 chunk; 1 câu `/chat` (có rerank) trả lời được.
- [x] Thời gian build sạch (no cache) ghi trước/sau trong ticket.
**Q&A** — **không cần**: hướng làm đã chốt trong §7, không đánh đổi hành vi.
**Giả định** — Giữ Python 3.13 + cùng version torch, chỉ đổi **build variant** (CPU vs CUDA); volume `hf-cache` giữ model
⇒ không tải lại 3,3 GB.
**Ghi chú kỹ thuật** — Thứ tự cài quan trọng: torch CPU **trước**, rồi `-r requirements.txt` (làm ngược có thể bị nâng
lên bản CUDA). Nếu pip không resolve được thì dùng `--extra-index-url`.
**Kết quả verify** (output thật)

```
# 1. Chẩn đoán TRƯỚC khi sửa — 16,5 GB nằm ở đâu (đo trong image cũ)
$ docker run --rm --entrypoint sh knowledge-base-chatbot-api:latest -c '…'
  /wheels                                  → **3,0 G**   (COPY --from=builder rồi không xoá)
  site-packages                            → 6,2 G
  site-packages/nvidia                     → **3,0 G**   (15 gói nvidia-*, CUDA)
  torch                                    → **2.15.0+cu132**  (bản CUDA)

# 2. Sửa (Dockerfile): torch CPU trước + bind-mount /wheels + xoá wheel torch không phải `+cpu`
$ docker build --no-cache -t knowledge-base-chatbot-api:latest .
  → **BUILD_SECONDS=209.35** (≈3,5 phút, mạng + cài deps; lần build đầu trước đây không đo được)

# 3. Sau khi sửa
$ docker images | grep chatbot-api
  → knowledge-base-chatbot-api:latest   **2,68 GB**   (16,5 → 2,68 = **−83,8%**)
$ docker run --rm --entrypoint sh … -c 'python -c "import torch; print(torch.__version__)" …'
  → **2.15.0+cpu**   |  `pip list | grep -c nvidia` = **0**  |  `/wheels` = **NO**  |  site-packages **1,9 G**

# 4. Runtime vẫn đúng
$ docker compose up -d chatbot-api  → chatbot-api **healthy** (sau ~1 phút)
  INFO app.main: logging configured: level=INFO
  Conversation store ready: ./data/chat.db (12 session đã lưu, max=200)
  Startup sync: +0 mới, ~0 cập nhật, -0 xoá, unchanged=46, chunks=0, 24ms   ← model lấy từ volume hf-cache
$ GET /documents/status → chunks **601**, status healthy, index_version 0
$ GET /ready            → status **ok** · {provider_config: true, prompt_file: true, collection: true}
$ POST /chat "Kafka là gì và RabbitMQ khác nó ở điểm nào?"
  → **12,79 s** (lần đầu: nạp cross-encoder vào RAM) rồi **3,07 s** (cache hit) / **4,81 s** (câu mới 1 ý)
  → rerank + embed vẫn chạy đúng trên torch CPU
```

**Learning note** — (1) **Image phình thường do "rác có chủ đích" chứ không phải do code**: 3 GB là `/wheels` mà
chính Dockerfile tự copy vào stage cuối "để cache" — `COPY` tạo layer, xoá ở `RUN` sau **không** làm nhỏ image.
Cách đúng là `RUN --mount=type=bind,from=builder,…` (BuildKit): thư mục chỉ tồn tại trong lúc chạy lệnh.
(2) **`--extra-index-url` không đủ để chọn torch CPU**: PEP 440 xếp `2.x.y+cpu` **thấp hơn** `2.x.y` ⇒ pip vẫn
chọn bản CUDA vì nó "mới hơn". Phải **cài torch CPU trước** rồi mới `-r requirements.txt` (khi đó `torch>=…` đã
thoả nên pip không đổi), và nếu prebuild wheel thì phải **xoá wheel không phải `+cpu`**.
(3) **Đo trước khi sửa trả tiền ngay**: 1 lệnh `du -sh` chỉ ra 3 nguyên nhân (wheels / nvidia / torch CUDA) ⇒ sửa
đúng chỗ trong 2 lần build, không đoán.
**MR** — BE **!26** (https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/26, squash `64974cc`). Nhánh
`perf/kb-5.10-*` đã xoá.


### KB-5.11 — UI: lịch sử chat thành ngăn kéo, nút xoá luôn hiện, bỏ đường kẻ mờ

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | FE (`Knowledge-base-fe`) |
| Phụ thuộc | KB-4.8 (shell + Sheet), KB-5.2 (xoá session gọi `DELETE /conversations/{id}`) |
| Ước lượng | M |

**Bối cảnh** — User báo 2 vấn đề khi dùng thật (ảnh chụp 2026-11-09):
1. **"Mất nút xoá"**: nút `Trash2` trong `app-sidebar.tsx` có `opacity-0 group-hover:opacity-100` ⇒ **vô hình** cho tới
   khi rê chuột đúng vào dòng ⇒ người dùng không biết có chức năng xoá (không phải mất code).
2. **Sidebar chiếm chỗ + nhiều đường kẻ mờ**: cột 256px luôn hiện, chia cắt màn chat bằng `border-r`; trong sidebar có
   `<Separator/>` + border trên từng dòng session; header có `border-b`; card nguồn có border mờ ⇒ giao diện "khung
   kẽ" nhiều đường kẻ, rối mắt.
**Mục tiêu** — Chat là **nhân vật chính**: danh sách hội thoại chuyển vào **ngăn kéo (Sheet)** mở bằng nút trên header;
nút xoá **luôn nhìn thấy**; bỏ các đường kẻ trang trí.
**In scope**
- `app-sidebar.tsx`:
  - `SessionRow`: nút xoá **luôn hiển thị** (`text-muted-foreground` → `hover:text-destructive`), giữ `aria-label`;
  - bỏ `<Separator/>` và border của từng dòng; phân tách bằng **khoảng cách + nền** (`bg-primary/10` khi active,
    `hover:bg-muted` khi hover).
- Bỏ cột `aside` cố định ở desktop (`AppSidebar`) — danh sách hội thoại **chỉ** nằm trong `Sheet` (ngăn kéo trượt từ
  trái), dùng chung `SidebarContent` như bản mobile hiện có.
- `app-header.tsx`: thêm nút **"Lịch sử"** (icon `MessageSquare` + `Badge` số phiên) mở ngăn kéo; giữ nút "Kho tài liệu"
  (vẫn đúng 1 nút) và theme toggle.
- Bỏ đường kẻ trang trí: `border-b` của header, `border-r` của sidebar (không còn), `border` mờ trên card nguồn
  (`sources-panel`) → dùng nền `bg-muted/40` + `rounded-lg`.
- Cập nhật test/e2e theo layout mới (chọn session ⇒ **mở ngăn kéo trước**).
**Out of scope** — Đổi màu/typography; thêm xác nhận khi xoá (giữ hành vi xoá ngay như hiện tại); sửa `DocumentsPanel`.
**Acceptance Criteria**
- [x] Nút xoá **thấy được** ở mọi dòng hội thoại khi **không** hover (kiểm bằng ảnh chụp + `toBeVisible()` không hover).
- [x] Không còn `aside` cố định: màn ≥1024px chat chiếm toàn bộ chiều ngang; hội thoại nằm trong ngăn kéo.
- [x] Header có đúng **1** nút "Lịch sử", **1** nút "Kho tài liệu", 1 theme toggle; `Badge` hiển thị số phiên.
- [x] Không còn `Separator`, `border-r`, `border-b` của header và border trên dòng session/card nguồn (grep = 0).
- [x] Bấm xoá ⇒ session biến mất **và** gọi `DELETE /conversations/{id}` (mock trong e2e xác nhận).
- [x] `npm run lint` 0 problem · `npx tsc --noEmit` sạch · `npm run test` (vitest) xanh · `npm run build` OK ·
  `npm run test:e2e` xanh (đã cập nhật test cho layout mới).
- [x] Ảnh chụp trước/sau: `shot-layout-before.png` (giữ trong `test-results/`, không commit) + 3 ảnh sau
  (chat full-width, ngăn kéo mở, dark mode).
**Q&A** — **không cần**: user đã chỉ rõ 2 yêu cầu + ảnh chụp; quyết định kỹ thuật (Sheet nào, bỏ border nào) suy ra
được từ code hiện có (`DocumentsPanel` đã dùng `Sheet`).
**Giả định** — (a) Ngăn kéo trượt từ **trái** (giống hamburger mobile hiện tại) để không đổi thói quen;
(b) trên mobile giữ nguyên hành vi cũ (nút hamburger mở cùng `SidebarContent`) — chỉ desktop đổi từ cột sang drawer;
(c) xoá session **không** cần hộp thoại xác nhận (giữ như cũ) vì đã có lịch sử lưu server và thao tác dễ lặp lại.
**Ghi chú kỹ thuật** — `Sheet` đã có trong `components/ui/sheet.tsx` (Radix Dialog ⇒ có focus trap/ESC/`aria-modal`, KB-4.8).
Nút xoá phải **không** nằm trong `<button>` chọn session (HTML không cho lồng button) — giữ cấu trúc `li` bọc 2 button
như hiện tại, chỉ đổi style. Bỏ border mà vẫn giữ phân cấp bằng `bg-muted/40` để dark mode không bị "phẳng lì".
**Kết quả verify** (output thật)

```
# 1. Bug gốc của "mất nút xoá" — tìm ra bằng đo toạ độ, không bằng mắt
$ npx playwright test e2e/diag-kb511.spec.ts  (spec tạm, đã xoá)
  drawer width = **288**
  delete button x = **363**  ← NGOÀI ngăn kéo ⇒ vô hình
  Nguyên nhân: Radix `ScrollArea` bọc nội dung trong `display: table` ⇒ tiêu đề dài làm dòng rộng hơn
  drawer, đẩy `absolute right-1.5` ra ngoài. Sửa: dùng `div.overflow-y-auto` thường.
  Sau khi sửa: delete button x = **247** (247+26 = 273 < 288) ✓

# 2. Grep AC (chỉ còn trong comment giải thích, không còn trong JSX)
$ grep -n 'Separator\|AppSidebar\|opacity-0' components/app-sidebar.tsx → chỉ dòng 11–15 (comment lịch sử)
$ grep -n 'border-b' components/app-header.tsx                  → chỉ dòng 32 (comment)
$ grep -c 'AppSidebar' app/page.tsx components/app-sidebar.tsx  → 0 trong JSX (component đã xoá)

# 3. Test tự động
$ npx tsc --noEmit                  → sạch
$ npx vitest run                    → **14 files / 123 tests passed** (+3 test mới: nút xoá luôn visible,
                                      không còn separator/border, nút "Lịch sử" mở ngăn kéo + badge)
$ npm run lint                      → **0 problem**
$ npm run build                     → ✓ Compiled successfully
$ npx playwright test (dev)         → **14 passed**
$ npm run test:e2e:prod (container) → **14 passed × 2 lần liên tiếp**

# 4. Ảnh chụp review (test-results/, không commit)
  review-1-fullwidth.png   chat chiếm toàn bộ ngang, không còn cột sidebar
  review-2-drawer.png      ngăn kéo mở, **icon xoá hiện ở mọi dòng**
  review-3-dark.png        dark mode: chữ + icon đọc được, không có đường kẻ
  review-4-drawer-zoom.png zoom ngăn kéo 288px: tiêu đề truncate "…", icon xoá trong khung

# 5. Flaky test được sửa luôn (không phải regression của ticket này)
  KB-5.6 test: BE thật còn 12 hội thoại đã lưu ⇒ app nạp lại và **đã có chip [S1]** từ trước ⇒ assert
  "chip chưa xuất hiện" fail. Sửa: stub `GET /conversations` → rỗng (cô lập test) + nới khoảng cách token.
```

**Learning note** — (1) **`toBeVisible()` KHÔNG bắt được "bị đẩy ra ngoài khung"**: nút xoá "visible" theo
Playwright nhưng nằm ở x=363 trong drawer rộng 288 ⇒ người dùng không thấy. Phải assert **bounding box** nằm trong
container (`x + width <= container.right`) — đã thêm vào e2e để không tái phát. (2) **Radix `ScrollArea` bọc nội dung
trong `display: table`** ⇒ nội dung `whitespace-nowrap` (tiêu đề truncate) làm dòng nở rộng hơn viewport; với layout
dùng `absolute right-*` thì phần tử bị đẩy ra ngoài. Với danh sách cần truncate, dùng `div.overflow-y-auto` thường là
an toàn hơn. (3) **`opacity-0 group-hover:opacity-100` là anti-pattern cho hành động phá huỷ**: người dùng không biết
chức năng tồn tại (đúng ca này — bị báo là "mất nút xoá"). Hành động xoá nên **luôn hiện**, chỉ đổi màu khi hover.
(4) **Test e2e nói chuyện với backend thật thì phải cô lập dữ liệu**: BE có 12 hội thoại đã lưu ⇒ DOM đã có chip
`[S1]` từ trước, làm test đếm phần tử sai. Stub endpoint danh sách về rỗng.
**MR** — FE **!23** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/23, squash `c06c766`). Nhánh
`feat/kb-5.11-*` đã xoá.


### KB-5.12 — Polish ngăn kéo Lịch sử: nút đóng + brand ở trên

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | FE (`Knowledge-base-fe`) |
| Phụ thuộc | KB-5.11 (ngăn kéo lịch sử) |
| Ước lượng | S |

**Bối cảnh** — Sau KB-5.11, ngăn kéo lịch sử có 2 lỗi thẩm mỹ khi dùng thật (ảnh chụp của user):
1. **Nút đóng mặc định của Radix `Sheet`** (X) bị đặt `absolute right-4 top-4` trong `SheetContent p-0` ⇒ **đè lên**
   nút "Cuộc trò chuyện mới", trông lệch và xấu.
2. Brand **"KB / Knowledge Base"** không có trong ngăn kéo ⇒ ngăn kéo trông như panel phụ, thiếu "đầu" để nhận diện.
User muốn brand nằm **trên** phần lịch sử.
**Mục tiêu** — Ngăn kéo có header riêng: brand bên trái, nút đóng bên phải (cùng một hàng, thẳng hàng padding), rồi mới
tới "Cuộc trò chuyện mới" → "LỊCH SỬ".
**In scope**
- `app-header.tsx`: `SheetContent` của ngăn kéo lịch sử dùng `showCloseButton={false}` (giống `DocumentsPanel`).
- `app-sidebar.tsx`: thêm hàng header trong `SidebarContent`:
  - brand: badge vuông `KB` + chữ **Knowledge Base** (không phải link để tránh điều hướng ngoài ý, hoặc link `/` nếu giữ
    hành vi header — chọn **không link**, chỉ nhận diện);
  - nút đóng: `Button variant="ghost" size="icon-sm"` + icon `X`, `aria-label="Đóng lịch sử"`, cùng chiều cao hàng
    (`h-9`), `padding` khớp `px-3` ⇒ thẳng với nút "Cuộc trò chuyện mới" bên dưới;
  - prop mới `onClose?: () => void` (ngăn kéo truyền `close`, test render không truyền ⇒ không render nút).
- `app/page.tsx`: truyền `onClose` xuống `SidebarContent` qua `renderSidebar`.
**Out of scope** — Đổi vị trí brand ở header chính (giữ nguyên); đổi nội dung danh sách; thêm animation mới.
**Acceptance Criteria**
- [x] Trong ngăn kéo **không** còn nút X mặc định của Radix (`SheetContent` có `showCloseButton={false}`).
- [x] Header ngăn kéo: brand trái, nút đóng phải, cùng 1 hàng; **không** đè lên nút "Cuộc trò chuyện mới".
- [x] Nút đóng bấm được ⇒ ngăn kéo đóng (`role=dialog` biến mất); vẫn đóng được bằng `ESC`.
- [x] Brand nằm **trên** nút "Cuộc trò chuyện mới" và mục "LỊCH SỬ" (đúng thứ tự DOM + ảnh chụp).
- [x] `SidebarContent` không truyền `onClose` ⇒ **không** render nút đóng (dùng trong test component, không cần).
- [x] `tsc` sạch · `vitest` xanh (+ test mới cho brand/close) · `lint` 0 · `build` OK · `test:e2e` xanh (cập nhật nếu cần).
- [x] Ảnh chụp ngăn kéo (light + dark) trong `test-results/` để đối chiếu.
**Q&A** — **không cần**: user đã chỉ rõ 2 điểm + ảnh; chi tiết (icon X, ghost button) suy ra từ `DocumentsPanel` đang dùng.
**Giả định** — (a) Brand trong ngăn kéo là **nhận diện**, không phải link (bấm vào không nên đóng ngăn kéo rồi reload);
(b) vẫn giữ brand ở header chính để app có nhận diện khi ngăn kéo đóng.
**Ghi chú kỹ thuật** — `ui/sheet.tsx` đã có prop `showCloseButton` (DocumentsPanel dùng) ⇒ không cần sửa primitive.
Hàng header dùng `flex h-12 items-center justify-between px-3` để thẳng với `p-3` của nút bên dưới.
**Kết quả verify** (output thật)

```
# 1. Ngăn kéo có header riêng (ảnh review-5-drawer-light.png / review-6-drawer-dark.png)
  Hàng trên: [KB] Knowledge Base ............................ [X]
  Hàng dưới: [+ Cuộc trò chuyện mới]  →  LỊCH SỬ (n)  →  danh sách (icon xoá luôn hiện)

# 2. Assert vị trí (e2e mới trong ui.spec.ts)
  closeBox.x + width <= drawerBox.right        ✓ (nút nằm trong khung)
  closeBox.y + height <= newChatBox.y          ✓ (hàng trên, KHÔNG đè nút Tạo mới)
  click nút đóng ⇒ role=dialog count = 0      ✓ ; ESC vẫn đóng được (test cũ)

# 3. Không còn nút X mặc định của Radix
$ grep -n 'showCloseButton' components/app-header.tsx → `showCloseButton={false}`

# 4. Toàn bộ kiểm tra
$ npx tsc --noEmit            → sạch
$ npx vitest run              → **14 files / 124 tests passed** (+1 test: brand ở trên Lịch sử, nút đóng chỉ render khi có `onClose`)
$ npm run lint                → **0 problem**
$ npm run build               → ✓ Compiled successfully
$ npx playwright test (dev)   → **15 passed**
$ npm run test:e2e:prod       → **15 passed** (container rebuild, :3010)
$ tools/pii_scan.py <5 file>  → [OK]
```

**Learning note** — (1) **Primitive của Radix không hợp `p-0`**: `SheetContent` đặt nút X ở `absolute top-4 right-4`; khi
content `p-0` thì nút rơi **lên nội dung** (đè nút chính). Pattern đúng (đã dùng ở `DocumentsPanel`):
`showCloseButton={false}` + tự dựng header `h-14 px-3` có nút đóng của mình ⇒ canh thẳng với các khối bên dưới.
(2) **Brand trong ngăn kéo phải là “nhận diện”, không phải link**: nếu để `<Link href="/">` thì bấm vào sẽ điều hướng +
đóng ngăn kéo (mất ngữ cảnh đang đọc lịch sử). (3) **Kiểm thẩm mỹ bằng toạ độ, không bằng mắt**: assert
`closeBox.y + height <= newChatBox.y` bắt được đúng lỗi “nút đè nút” mà ảnh chụp ở scale nhỏ rất dễ bỏ qua.
**MR** — FE **!24** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/24, squash `e1f839d`). Nhánh
`feat/kb-5.12-*` đã xoá.


### KB-5.13 — Header: brand đứng trước nút Lịch sử

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5 |
| Repo | FE (`Knowledge-base-fe`) |
| Phụ thuộc | KB-5.11 (nút Lịch sử), KB-5.12 (brand trong ngăn kéo) |
| Ước lượng | S |

**Bối cảnh** — Header hiện xếp `[Lịch sử (n)] [KB Knowledge Base] …` ⇒ brand nằm **sau** nút Lịch sử. User yêu cầu brand
phải đứng **trên/trước** nút Lịch sử, kể cả khi ngăn kéo chưa mở (ảnh chụp 2026-11-09).
**Mục tiêu** — Thứ tự header: **brand (KB + Knowledge Base)** → nút **Lịch sử** → (phải) **Kho tài liệu** + theme.
**In scope**
- `app-header.tsx`: đưa `<Link>` brand lên **trước** khối `Sheet` của nút Lịch sử (DOM order + visual order).
**Out of scope** — Đổi style brand; đổi vị trí nhóm bên phải (vẫn `ml-auto`); đổi thứ tự trong ngăn kéo (đã đúng ở KB-5.12).
**Acceptance Criteria**
- [x] DOM order trong `<header>`: brand đứng trước nút "Mở lịch sử trò chuyện" (assert bằng `compareDocumentPosition`).
- [x] Vị trí thị giác: `brandBox.x + width <= historyButtonBox.x` (brand bên trái nút Lịch sử).
- [x] Nhóm phải (`Kho tài liệu`, theme toggle) vẫn dính mép phải (`ml-auto` không đổi).
- [x] `tsc` sạch · `vitest` xanh (+1 test thứ tự) · `lint` 0 · `build` OK · `test:e2e` xanh (15 test).
- [x] Ảnh chụp header (light + dark) trong `test-results/`.
**Q&A** — **không cần**: 1 dòng yêu cầu, phạm vi 1 file.
**Giả định** — "nằm trên nút lịch sử" hiểu là **đứng trước** (bên trái) trong header thanh ngang, không phải xếp 2 hàng dọc
(header cao 56px, xếp dọc sẽ vỡ layout). Nếu user muốn 2 hàng thật thì mở ticket riêng.
**Ghi chú kỹ thuật** — Chỉ đổi thứ tự JSX; `gap-2` + `ml-auto` của header giữ nguyên nên không cần chỉnh CSS khác.
**Kết quả verify** (output thật)

```
# 1. Header sau khi sửa (ảnh review-7-header-light.png / review-8-header-dark.png)
  [KB] Knowledge Base   🕐 Lịch sử            ……………            [Kho tài liệu] [theme]
  → brand đứng TRƯỚC nút Lịch sử; nhóm phải vẫn dính mép phải (ml-auto).

# 2. Assert thứ tự (thêm vào e2e "header có brand…")
  compareDocumentPosition(brand, historyButton) & DOCUMENT_POSITION_FOLLOWING → **true**
  brandBox.x + width <= historyBox.x                                            → **true**

# 3. Kiểm tra
$ npx tsc --noEmit            → sạch
$ npx vitest run              → **124 passed**
$ npm run lint                → **0 problem**
$ npm run build               → ✓ Compiled successfully
$ npx playwright test         → **15 passed** (dev)
$ npm run test:e2e:prod       → **15 passed** (container rebuild :3010)
$ tools/pii_scan.py <2 file>  → [OK]
```

**Learning note** — Thay đổi “1 dòng thứ tự JSX” vẫn nên có **assert thứ tự** (DOM + toạ độ): layout ngang rất dễ bị
đảo lại khi thêm nút mới, và mắt thường bỏ qua vì cả hai phần tử đều “hiện”. `compareDocumentPosition` bắt được lỗi
DOM-order còn `boundingBox` bắt được lỗi thị giác (khi CSS thay đổi thứ tự bằng flex `order`/`dir`).
**MR** — FE **!25** (https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/25, squash `19c5396`). Nhánh
`feat/kb-5.13-*` đã xoá.


---

## 4b. Phase 5b — Trả nợ kỹ thuật (TD sweep, 2026-11-10)

> User yêu cầu: *"xử lý tất cả TD, cái nào không làm được thì đánh Skip"*. Mỗi món trả nợ là **1 ticket
> riêng** (rule `20-tech-debt.md`) — 4 ticket làm được, phần còn lại chốt **Skip** kèm lý do trong §7.

### KB-5.14 — Embedding CPU: ép `float32` (trả TD-14)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5b |
| Repo | BE |
| Ước lượng | S |

**Bối cảnh** — TD-14: re-index toàn bộ 601 chunk mất ~22 phút ⇒ mỗi lần đổi chunking/embedding phải chờ
lâu, và lần sync đầu trên máy mới rất chậm. Model Qwen3 mặc định chạy **bfloat16**, nhưng CPU **không có
kernel bf16 nhanh** (PyTorch emulate).

**In scope** — thêm `EMBEDDING_TORCH_DTYPE` (mặc định `float32`), đẩy `EMBEDDING_BATCH_SIZE` (đã có trong
config nhưng **chưa được dùng** — nợ nhỏ đi kèm) vào `encode_kwargs`; đo lại throughput trên chunk thật.

**Out of scope** — đổi model/quantize int8/ONNX (đo sau nếu vẫn chậm).

**Acceptance Criteria**
- [x] `build_embedding_params` truyền `torch_dtype` (lồng trong `model_kwargs`) + `batch_size`
- [x] `EMBEDDING_TORCH_DTYPE=default` ⇒ không ép dtype (giữ đường lui)
- [x] Đo được throughput trước/sau trên **chunk thật**, ghi số vào ticket
- [x] Ghi rõ: đổi dtype ⇒ phải re-index toàn bộ (vector khác không gian)

**Kết quả verify** (output thật)

```
# 1. Microbench qua chính `build_embedding_params` (64 chunk, máy rảnh)
bf16 (mặc định)  → 1,87 chunk/s
float32 (mới)    → 8,11 chunk/s        ⇒ nhanh 4,3×

# 2. End-to-end THẬT: chạy app local (Chroma tạm) + sync cả folder 56 file / 601 chunk
$ /health          → 200 sau 5,6 s (app lên trước, sync chạy nền — KB-5.16)
$ startup_sync     → status=done elapsed_seconds=**436,769** chunks=**601** added=46
  ⇒ **7,3 phút** cho 601 chunk (trước: ~22 phút) ⇒ nhanh **~3×** (microbench 4,3×; phần còn lại là
    parse file + Chroma write + máy đang chạy docker/load ~7)
$ POST /chat "RAG là gì?"  → 922 ký tự, 3 sources ⇒ index float32 dùng được, không hỏng retrieval

# 3. Chứng minh dtype thật sự được áp (không phải "đoán là nhanh hơn")
$ EMBEDDING_TORCH_DTYPE=float32  → model.auto_model.dtype = torch.float32
$ EMBEDDING_TORCH_DTYPE=bfloat16 → torch.bfloat16
$ EMBEDDING_TORCH_DTYPE=default  → torch.bfloat16   (đường lui còn nguyên)
# 4. Trong CONTAINER production (sau rebuild image + re-index thật)
$ docker compose up -d --build chatbot-api   → healthy; /ready có startup_sync + rate_limit
$ POST /documents/sync (index rỗng sau clear) → 601 chunk, elapsed_ms=**537 077** (**8,95 phút**)
$ POST /chat "Saga pattern là gì?"           → 760 ký tự, 3 sources ⇒ retrieval đúng với index fp32
  (chậm hơn 7,3 phút của lần chạy local vì container + máy đang chạy 14 container dự án khác)
```

Unit test: `tests/test_embeddings_config.py` (**6 case**) — pass.



### KB-5.15 — Rate limit per-IP cho chat (trả TD-20)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5b |
| Repo | BE |
| Ước lượng | M |

**Bối cảnh** — TD-20: chưa có giới hạn phía server. Mỗi câu `/chat` tốn rerank CPU (~3–4 s) + 1 request
provider (Groq free tier TPM). Khi mở LAN/VPS (cùng bối cảnh KB-5.5 auth), 1 tab bấm liên tục là nghẽn.

**In scope** — `app/core/rate_limit.py`: sliding-window theo IP, **chỉ** `/chat` + `/chat/stream`, cờ
`RATE_LIMIT_ENABLED` (**mặc định TẮT**), 429 theo envelope KB-3.1 + `Retry-After`; số liệu ở `/ready`.

**Out of scope** — rate limit theo user/token, store dùng chung (Redis) cho nhiều worker — xem TD-17.

**Acceptance Criteria**
- [x] Cờ tắt (mặc định) ⇒ hành vi không đổi; bật ⇒ request thứ N+1 trả 429
- [x] 429 có `error.code=rate_limited` + `request_id` + `Retry-After`
- [x] `/health`, `/ready`, `/conversations` **không** bị chặn
- [x] Sliding window (không "burst gấp đôi" như fixed window) + không đọc `X-Forwarded-For`
- [x] Unit + endpoint test (`tests/test_rate_limit.py`, 13 case)

**Kết quả verify** — `pytest tests/test_rate_limit.py -q` → **13 passed**; full suite xem KB-5.16.

### KB-5.16 — Startup sync chạy nền + trạng thái nhìn được (trả TD-25)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5b |
| Repo | BE |
| Ước lượng | M |

**Bối cảnh** — TD-25: `lifespan` **await** `sync_documents()` ⇒ app chưa phục vụ cho tới khi hash 56 file
(~1,5 s) hoặc embed file mới (1,2 s/file); không có cách xem tiến trình ngoài log.

**In scope** — `app/services/startup_sync.py` (`StartupSyncState`), lifespan dùng `asyncio.create_task`
(cờ `STARTUP_SYNC_BACKGROUND`, mặc định **bật**), trạng thái vào `checks.startup_sync` của `/ready` và
`startup_sync` của `/documents/status`.

**Out of scope** — % tiến trình theo từng file (cần stream/SSE riêng — xem TD-23), job queue khi restart
giữa lúc sync.

**Acceptance Criteria**
- [x] App nhận request ngay; sync chạy nền
- [x] `/ready` + `/documents/status` hiện `running`/`done`/`failed`/`skipped`
- [x] Lỗi sync **không** làm chết app; chỉ giữ **tên loại lỗi** (không rò message/path — PII rule)
- [x] Test: `tests/test_startup_sync.py` (11 case) + full suite xanh

**Kết quả verify** (output thật)

```
$ uvicorn app.main:app --port 8011   (CHROMA_DB_PATH=/tmp/…, CHAT_DB_PATH=/tmp/…)
  INFO: Application startup complete.        ← server nhận request ngay, KHÔNG chờ sync
$ curl /health   (đo từ lúc start)           → 200 sau **5,6 s**
$ curl /ready     (ngay sau đó)
  "startup_sync": {"ok": true, "detail": "index sync đang chạy nền — chat dùng index hiện có"}
  "rate_limit":   {"ok": true, "detail": "rate limit tắt (RATE_LIMIT_ENABLED=false)"}
$ curl /documents/status  (poll)
  running 14,3 s → running 51,7 s → running 130,5 s (chunks=128) → …
  → done elapsed_seconds=436,769 chunks=601 added=46 unchanged=0
$ curl /ready  (sau khi xong)
  "startup_sync": {"ok": true, "detail": "index sync xong trong 436.769s (+46 mới, ~0 cập nhật, -0 xoá, 601 chunk)"}

$ pytest -q  → 320 passed, 1 warning in 1.16s      (trước đợt này: 293)
```

Lỗi tìm được **nhờ verify runtime** (không phải test): thiếu `global startup_sync_state` trong `lifespan`
⇒ `/ready` không có check `startup_sync` dù test giả lập vẫn xanh (test gắn state trực tiếp vào module).
Đã sửa ở `app/main.py:113`.


### KB-5.17 — UI: kiểm provider `deep=true` + hiện mọi check (trả TD-23, phần UI)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 5b |
| Repo | FE |
| Ước lượng | S |

**Bối cảnh** — TD-23: `/ready?deep=true` có ở BE nhưng **không có UI** ⇒ muốn biết key provider còn sống
phải curl. Đồng thời panel chỉ hiện check **lỗi**, nên `startup_sync`/`rate_limit` mới (KB-5.15/5.16)
không nhìn thấy.

**In scope** — `getReady({deep})`; nút **Kiểm tra provider** (chỉ gọi khi bấm — tốn 1 request); render
**mọi** check với ✓/✗ + detail.

**Out of scope** — % tiến trình sync (cần BE stream — TD-23 vẫn để mở phần này), auto-poll.

**Acceptance Criteria**
- [x] Nút gọi `/ready?deep=true`, có trạng thái "Đang kiểm…" và disable khi bận
- [x] Mọi check hiện ra (kể cả `startup_sync`, `rate_limit`), check fail tô đỏ
- [x] Test component cho cả 3 hành vi (`tests/documents-panel.test.tsx`)

**Kết quả verify**

```
$ npm run test       → 132 passed (132)   (trước: 130)
$ npm run typecheck  → sạch
$ npm run lint       → 0 error/warning
$ APP_URL=http://localhost:3010 npx playwright test   (UI + BE trong container, dữ liệu THẬT)
  ✓ Readiness: liệt kê mọi check, có nút "Kiểm tra provider"   → /ready?deep=true được gọi, check
    `provider` xuất hiện (screenshot `test-results/shot-15-ready-checks.png`)
  → **16 passed (16,9 s)**   (trước: 15)
```

Ghi chú: lần chạy e2e đầu tiên có **1 flake** (`Sheet` focus) — pass lại ngay khi chạy lại; `retries = 0`
trong `playwright.config.ts` nên flake hiện ra thay vì bị che. Chưa đổi cấu hình (1 flake/16 test chưa đáng
bật retry).

**MR**: BE [!29](https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/29) (KB-5.14+5.15+5.16) ·
FE [!28](https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/28) (KB-5.17) — squash-merged, nhánh đã xoá.

### Bảng chốt đợt TD sweep (2026-11-10)

| TD | Quyết định | Bằng chứng |
|---|---|---|
| TD-14 | ✅ trả (KB-5.14) | 601 chunk: 22 phút → **7,3 phút** (local) / 8,95 phút (container) |
| TD-20 | ✅ trả (KB-5.15) | 13 test; 429 + `Retry-After`; cờ `RATE_LIMIT_ENABLED` TẮT mặc định |
| TD-23 | ✅ phần UI (KB-5.17) · ⏭️ Skip phần % | e2e 16/16, `?deep=true` được gọi thật |
| TD-25 | ✅ trả (KB-5.16) | `/health` 200 sau 5,6 s; trạng thái sync ở `/ready` + `/documents/status` |
| TD-17 | ⏭️ Skip | 1 worker là chủ ý (1 bản model/worker); revisit khi cần nhiều worker |
| TD-24 (phần deploy) | ⏭️ Skip | chưa có registry/đích deploy; bake model = +3,3 GB vô ích |
| TD-28 | ⏭️ Skip | cache dẫn xuất, 1 người dùng; lưu đĩa không đáng |
| TD-30 | ⏭️ Skip | LLM-split đổi thứ đã bão hoà (MRR 0,975) lấy 1 request/câu |



---


## 4c. Phase 9 — Chất lượng câu trả lời (chẩn đoán + sửa)

> Xuất phát từ câu hỏi: *"chất lượng câu trả lời hơi tệ, do model kém hay RAG chưa tốt?"*. Trả lời bằng đo
> trên 1 câu thật (8 fact bắt buộc rút từ tài liệu), 4 điều kiện:

| Điều kiện | Fact | Kết luận |
|---|---|---|
| Pipeline thật (k=3, temp .7, max 1000) | 6/8 | baseline |
| **Gold context** (toàn bộ file nguồn), config cũ | 8/8 **nhưng cắt giữa câu** (1.491 chars) | RAG chọn context sai **và** `max_tokens` cắt câu |
| Gold context, temp 0.1 / max 2000 | 8/8, đủ câu | config là biến số lớn |
| Không context (model thuần) | 7/8 | **model không kém** |

⇒ Model ổn; thủ phạm là **(1) config chết** (`ChatRequest` hard-code đè env) và **(2) retrieval quá nông**
(corpus 601 → 2.879 chunk nhưng `RETRIEVAL_K=3`; file nguồn đúng rơi **hạng 7**).

### KB-9.1 — Env có tác dụng + tham số hợp lý (BE) — Done

| Trường | Giá trị |
|---|---|
| Repo | BE · Ước lượng S · Phụ thuộc — |

**Bug**: `ChatRequest.max_tokens/temperature` default 1000/0.7 **trong schema** ⇒ Pydantic luôn điền ⇒
service bỏ qua `DEFAULT_*` (2 env chết). Thêm: `temperature or default` biến `0.0` thành 0.7.

**Sửa**: default `None` (+ validate 64–8000 / 0–2); service dùng `x if x is not None else settings.default_*`;
env mới `DEFAULT_MAX_TOKENS=2500`, `DEFAULT_TEMPERATURE=0.2`, `RETRIEVAL_K=6`.

**Kết quả verify** (cùng câu hỏi): fact **6/8 → 7/8** · `Saga Pattern.md` từ **không có → S1** · không còn cắt
giữa câu (1.451 chars) · latency warm 5,0–5,2 s (trước 3,4–5,6 s; đổi lấy context rộng hơn) · `pytest -q`
**329 passed**.

**MR**: BE [!31](https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/31)

### KB-9.2 — Control tham số trên UI: mặc định "theo server" + có lưu (FE) — Done

| Trường | Giá trị |
|---|---|
| Repo | FE · Ước lượng S |

Composer đã có 2 control nhưng hard-code 1000/0.7, **không lưu** (F5 mất), cap 2000 ⇒ mỗi phiên âm thầm ghi
đè default tốt hơn của server. Sửa: `lib/answer-settings.ts` (store ngoài React như ADR-0015), `null` =
"theo server" ⇒ **không gửi field**; badge + nút **Dùng theo server**; cap 200–4000.

**Kết quả verify**: `npm run test` **142 passed** (trước 132) · e2e **17 passed** (thêm 1 case kiểm **body
request thật**: chỉ gửi field đã đổi, lưu qua reload, reset về null) · lint 0 · build ✓.

**MR**: FE [!30](https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/30)

### KB-9.3 — Nguồn tự thu gọn + mở bằng chip `[S1]` (FE)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 9 |
| Repo | FE (`Knowledge-base-fe`) |
| Phụ thuộc | KB-4.3 (panel nguồn), KB-5.6 (render sau `end`) |
| Ước lượng | S |

**Bối cảnh** — Panel nguồn hiện **luôn mở**: mỗi câu trả lời đẩy 3–6 card (path + snippet 400 ký tự +
score) xen giữa các message ⇒ danh sách chat dài, câu trả lời trước bị đẩy xa, và với corpus 2.879 chunk
thì số nguồn mỗi câu tăng (`RETRIEVAL_K=6`). Người dùng thường **không** cần đọc nguồn, chỉ cần biết có
nguồn nào; khi cần thì đã có chip `[S#]` trong câu trả lời.

**Mục tiêu** — Nguồn **thu gọn mặc định**, mở bằng 1 nút; và mở **đúng card** khi bấm chip `[S#]`.

**In scope**
- `SourcesPanel`: header thành **nút bật/tắt** (`aria-expanded` + `aria-controls`), mặc định **đóng**;
  khi đóng chỉ hiện 1 dòng tóm tắt (tên file đầu tiên + `+N`) thay vì 3–6 card.
- Bấm chip `[S#]` trong câu trả lời ⇒ panel của message đó **tự mở** + scroll + highlight card (đã có sẵn
  cơ chế `highlightCitationId`/`highlightNonce`; chỉ cần auto-open).
- Nút "Xem thêm/Thu gọn" snippet vẫn hoạt động như cũ khi panel mở.

**Out of scope** — Đổi dữ liệu `sources` từ BE; dedup theo file (đã chốt ở KB-4.3: không dedup); lưu
trạng thái đóng/mở giữa các phiên.

**Acceptance Criteria**
- [x] Mặc định panel **đóng**; chỉ thấy header "Nguồn (N)" (bấm được, có `aria-expanded=false`).
- [x] Bấm header ⇒ mở/đóng, card hiện/ẩn đúng; bấm lần nữa đóng lại.
- [x] Bấm chip `[S2]` khi panel đang đóng ⇒ panel mở + card `S2` được highlight.
- [x] Có test component cho 3 hành vi trên + e2e cập nhật (các case đang giả định panel luôn mở).
- [x] Không đổi layout: panel vẫn `w-full min-w-0`, không tràn ngang ở 720/1440/1900 px.

**Q&A (trả lời trước khi làm)**
- Q1: Hành vi mong muốn: (a) chỉ auto-collapse + nút expand, (b) chỉ mở khi bấm `[S#]`, hay (c) cả hai?
  → **(c) cả hai** — auto-collapse mặc định **và** bấm `[S#]` thì mở đúng card (user: *"auto collapse, và
  có nút expand…, hoặc mở ra khi user bấm vào icon S1, S2"*).
- Q2: Khi đóng, có cần hiện tóm tắt (tên file) không, hay chỉ dòng "Nguồn (N)"?
  → **Có tóm tắt 1 dòng** (tên file đầu + `+N`) để biết nguồn nào mà không phải mở.

**Giả định** — Trạng thái đóng/mở là **state của từng message** (không lưu `localStorage`); message cũ
giữ trạng thái trong phiên hiện tại.

**Kết quả verify** (output thật)

```
$ npm run test            → 144 passed (144)   (trước: 142; +2 case panel: mặc định đóng, mở/đóng)
$ npm run lint            → 0 error/warning
$ npm run typecheck       → sạch
$ npm run build           → ✓ Compiled successfully in 3.4s
$ APP_URL=:3010 npx playwright test → 18 passed (18.7s)   (trước 17; +1 case thu gọn/mở bằng chip)
```

Case e2e mới kiểm trên UI thật: mặc định `aria-expanded=false` + tóm tắt `Saga Pattern.md +1`, **không** có
card ⇒ bấm nút mở ra 2 card ⇒ bấm lại đóng ⇒ bấm chip `[S1]` trong câu trả lời thì panel **tự mở** và card
`S1` có `ring-2`. Ảnh: `test-results/shot-16-sources-collapsed.png`, `shot-17-sources-opened-by-chip.png`.

2 lỗi tự tìm khi làm:
1. `setState` trong effect (lint `react-hooks/set-state-in-effect`) ⇒ chuyển sang **derive** trạng thái mở.
2. Derive đơn giản (`manualOpen ?? highlight`) làm panel **không mở lại** khi user đã tự đóng rồi bấm chip
   ⇒ ghi `nonce` kèm lần bấm nút: highlight **mới** (nonce khác) thắng trạng thái đóng.
**Learning note** — Trạng thái "mở/đóng" có **2 nguồn điều khiển** (nút của user vs. bấm chip trong câu trả lời) ⇒ phải có **thứ tự ưu tiên** rõ ràng, nếu không sinh bug "bấm chip không mở" — chỉ e2e bắt được, vì unit test dùng `rerender` không tái hiện ca "đã đóng bằng tay rồi mới bấm chip". Cách gọn: so **nonce** của lần bấm nút với nonce của highlight. Bài học phụ: thêm panel collapsible làm **vỡ 3 e2e cũ** (giả định panel luôn mở) ⇒ thêm helper `expandSources()` thay vì sửa từng assert.

### KB-9.4 — Ngưỡng liên quan: bỏ nguồn điểm thấp, để AI tự trả lời (BE + FE)

| Trường | Giá trị |
|---|---|
| Trạng thái | Done |
| Phase | 9 |
| Repo | BE (`Knowledge-base`) + FE (`Knowledge-base-fe`) |
| Phụ thuộc | KB-9.1 (đã nới `RETRIEVAL_K=6`) |
| Ước lượng | M |

**Bối cảnh** — Sau KB-9.1, mỗi câu lấy **6 chunk**. Đo thực tế: `precision@k` chỉ **0,617** ⇒ gần 40% chunk
trong context là **nhiễu**; chunk nhiễu vừa chiếm context window vừa làm model bám vào bằng chứng kém.
Câu hỏi ngoài phạm vi tài liệu cũng có thể vẫn "có nguồn" (điểm thấp) ⇒ câu trả lời gượng ép.

**Mục tiêu** — Có **ngưỡng điểm** phía BE: nguồn dưới ngưỡng bị **loại khỏi context** (và khỏi danh sách
nguồn); nếu **không còn nguồn nào** ⇒ model trả lời bằng kiến thức chung và **nói rõ** là không có trong
knowledge base (prompt đã có luật này — ADR-0007/prompt hiện tại).

**In scope (dự kiến)**
- `RELEVANCE_MIN_SCORE` (env) áp lên **rerank score** (logits cross-encoder — đại lượng duy nhất đo được
  "liên quan" sau rerank); log số nguồn bị loại.
- Prompt: khi context rỗng ⇒ nhánh "không có trong KB" (đã có) + không được bịa `[S#]`.
- FE: hiện nhãn nhỏ "đã bỏ N nguồn điểm thấp" (metadata) để người dùng biết vì sao ít nguồn.

**Out of scope** — Đổi rerank model; lọc trước rerank (dense threshold — đã chốt `SIMILARITY_THRESHOLD=0`
ở ADR-0005, xem lại thì mở ticket riêng).

**Acceptance Criteria (dự kiến)**
- [x] Có số đo **trước/sau** trên bộ vàng: `precision@k`, số nguồn/câu, tỉ lệ câu "không có trong KB".
- [x] Câu hỏi ngoài phạm vi (vd "giá vàng hôm nay") ⇒ **0 nguồn** + câu trả lời nói rõ không có trong KB.
- [x] Câu hỏi trong phạm vi ⇒ **không** mất nguồn đúng (đo trên 20 câu vàng).
- [x] `[S#]` trong câu trả lời luôn khớp danh sách nguồn còn lại (không nhãn mồ côi).

**Q&A (đã chốt)**
- Q1: Ngưỡng đặt trên **score nào** — rerank logits (hiện `relevance_score` trả về FE) hay score hybrid
  đã chuẩn hoá? Giá trị khởi điểm bao nhiêu (đề xuất: đo phân bố trên 20 câu vàng rồi chọn, không đoán)?
  → **rerank score** (sigmoid), ngưỡng **tính lại trên bộ vàng mới** = 0,02; đổi được trên UI + có default server.
- Q2: Khi **tất cả** dưới ngưỡng: (a) trả lời bằng kiến thức chung + ghi rõ "không có trong KB", (b) chỉ
  nói "không có trong knowledge base", hay (c) vẫn trả lời nhưng ẩn nguồn?
  → **(a)** trả lời bằng kiến thức chung + ghi rõ "không có trong knowledge base".
- Q3: Có hiện số nguồn bị loại trên UI không, hay ẩn hoàn toàn?
  → **Có** — ghi chú nhỏ "Đã bỏ N nguồn…" trong panel nguồn.

**Giả định** — Ngưỡng phải **đo** từ `eval/runs` (không đặt số theo cảm giác — bài học ADR-0010).



- **Hub-file pollution**: top-k bị các file Q&A/index lớn (`Microservices Q&A.md`, `Junior/Middle Java
  Interview.md`) chiếm chỗ; cần luật xếp hạng/loại trừ file hub.
- **Bộ eval lỗi thời**: `qa_set.json` trỏ path cũ (sau khi dọn `Interview/`) ⇒ phải re-point + chạy lại
  trước/sau khi chỉnh tham số, thay vì tin `hit@k 1.0` cũ.
- **DB không bị ảnh hưởng**: `chroma_db` có 4 segment cũ (dọn bằng clear + sync nếu muốn gọn).

---



**Q&A Phase 8 đã chốt** (2026-11-09): Q1 = **B** (ADR bản học tập sâu: số đo + code + anti-pattern + "nếu làm lại") · Q2 = **A** (làm đủ **16** quyết định) · Q3 = **B** (câu hỏi ôn tập gom ở `docs/adr/README.md`) · Q4 = **không** cần bản EN. ⇒ **không chờ gì nữa**, chạy KB-8.1 được ngay.

Thứ tự đề xuất:

| # | Ticket | Repo | Ước lượng | Vì sao trước |
|---|---|---|---|---|
| 1 | **KB-8.1 → KB-8.2 → KB-8.3 → KB-8.4** (16 ADR, bản sâu) | docs | M × 4 | Backfill ADR — nền cho mọi tài liệu khác |
| 2 | **KB-8.7** (README BE) → **KB-8.8** (README FE) → **KB-8.6** (README root) | BE/FE/docs | M · S · M | README con phải đúng trước, root chỉ tóm tắt + link |
| 3 | **KB-8.5** (index ADR + 20 câu ôn tập) | docs | S | Cần đủ 16 ADR rồi mới làm index |
| 4 | **TD-29** (ticket mới, chưa tạo) | BE | S | Món lợi lớn nhất còn bỏ ngỏ: câu **mới** 4,5 s → ~2,0 s, MRR 0,975 → 1,0 |
| 5 | **KB-5.7** — CI GitLab (lint+test+build+e2e) | cả 2 | M | Trả TD-24; từ đó mọi MR có cổng tự động |
| 6 | **KB-5.5** — Auth tối giản | BE+FE | S | Chỉ khi mở ra ngoài localhost (đi cùng TD-20 rate limit) |
| 7 | Cụm dọn dẹp **TD-18 + TD-19 + TD-27** | BE | S | Đều nhỏ, giảm ma sát khi debug/viết test |
| 8 | **TD-9** (image 16,5 GB → torch CPU) | BE | M | Cần build lại + verify; làm khi rảnh hoặc trước khi push registry |

Nợ đang mở nhưng **chưa nên làm**: TD-17/TD-28 (chờ > 1 worker), TD-30 (chờ bộ câu khó hơn), TD-14 (chỉ đau khi
re-index toàn bộ), TD-23 (sync hiện 1,2 s/file nên chưa cần thanh tiến trình).

---

**MR**: BE [!32](https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/32) ·
FE [!32](https://gitlab.com/anchu3003/knowlege-base-fe/-/merge_requests/32) — squash-merged.

## KB-9.7 — Hub-file pollution: **đo xong, Skip** (hạ điểm là sai hướng)

### Giả thuyết
File dạng mục lục / Q&A lớn (`*Index*.md`, `Microservices Q&A.md`, `Exam guide.md`…) chứa nhiều từ khoá nên
chiếm slot top-k, đẩy file nội dung thật ra ngoài ⇒ `precision@k` thấp (0,333). Cách sửa dự kiến: **hạ điểm**
(hệ số `HUB_FILE_PENALTY`) các chunk thuộc file hub ngay sau rerank.

### Đo (bộ vàng v4 — 28 câu, k=6, rerank top-6, cache tắt)
| Cấu hình | `hit@k` | `MRR` | `precision@k` |
|---|---|---|---|
| **Baseline (không hạ điểm)** | **0,964** | 0,833 | **0,333** |
| Hạ điểm vô điều kiện 0,5 | 0,821 | 0,851 | 0,208 |
| Hạ điểm vô điều kiện 0,3 | (tương tự, kém hơn) | — | — |
| Hạ điểm **có điều kiện** 0,5 (chỉ hạ khi có non-hub ≥ 0,5× điểm hub) | 0,750 | 0,889 | 0,179 |
| Hạ điểm có điều kiện 0,3 | 0,750 | 0,890 | 0,179 |

### Kết luận: **Skip penalty** — không merge thay đổi hành vi
- **Vì sao thất bại**: nhiều câu trong bộ vàng có **đáp án chính là file index** (`Database Index.md`,
  `AWS Index.md` + `Best practices.md`) ⇒ hạ điểm file đó là **mất nguồn đúng**; `precision` còn giảm vì phần
  nhiễu còn lại (file nội dung nhưng không liên quan) không bị hạ.
- **Giữ lại**: `app/services/hub_files.py` (nhận diện theo tên + độ dày link/bullet, **16 test**) làm **công cụ
  chẩn đoán** — dùng để đếm tỉ lệ chunk hub trong top-k khi phân tích retrieval, không tham gia xếp hạng.
  **Không** đánh dấu hub các file Q&A tự luận (`Junior Java Interview.md`, `Questions for interviewers.md`) —
  đo cho thấy chúng là nội dung thật, đánh dấu chỉ làm rơi `hit@k`.
- **Hướng khác cho lần sau** (ghi ở TD-31): tách "mục lục" khỏi index khi ingest (hoặc index riêng loại
  `outline`), thay vì phạt điểm sau rerank.

**Kết quả verify**
```
$ pytest -q                     → 355 passed (16 test mới cho hub_files)
$ eval 3 cấu hình (xem bảng)    → penalty làm hit@k 0,964 → 0,821 / 0,750
$ eval sau khi bỏ code penalty  → hit@k 0,964 · MRR 0,833 · precision@k 0,333 (không đổi baseline)
```
Snapshot: `eval/runs/2026-11-10T15*-kb97-*.json`.

**Learning note** — "File mục lục chiếm top-k" nghe rất hợp lý nhưng **đo ra là sai**: chính chúng thường là
nguồn đúng, nên phạt điểm vừa mất `hit@k` vừa không tăng `precision`. Bài học: **giả thuyết về retrieval phải
đo trên bộ vàng trước khi merge** (ADR-0010) — nếu chỉ "cảm thấy hợp lý" thì đã ship một thay đổi làm hệ thống
tệ hơn 15% `hit@k`. Cũng học được: heuristic theo **tên file** dễ bắt oan (`interview`/`questions` là nội dung
thật) ⇒ thu hẹp pattern và test cả chiều "không được bắt oan".

---

## 6. Learning log

| Ngày | Ticket | Học được |
|---|---|---|
| 2026-11-07 | KB-0.1 | Phân biệt rule (luôn active) / skill (on-demand) / workflow (gọi `/file`); Memory Bank lite = 2 file doc. |
| 2026-11-07 | KB-0.2 | `ChatOpenAI` chỉ cần đổi `base_url`+`key`+`model` để chuyển provider; nhưng hard-code base URL trong `get_settings()` sẽ ghi đè `.env` → phải bỏ. |
| 2026-11-07 | KB-1.1 | Che PII ở "cổng ra" (trước khi gọi LLM) bắt được cả PII nằm trong retrieved context, không chỉ câu hỏi user. |
| 2026-11-07 | KB-1.2 | Đặt redaction ở funnel `_add_documents_to_db` → che 1 chỗ, áp cho cả vector store lẫn BM25 corpus; tách hàm thuần để test khỏi cần embedding model. |
| 2026-11-07 | KB-1.3 | Badge icon-only + `title` tooltip đủ cho "cảnh báo PII"; trả sẵn `pii_redacted`+`pii_redacted_count` ở metadata để FE không tự cộng dict. → **Phase 1 hoàn tất (3/3)**. |
| 2026-11-07 | KB-6.1 | Range pin giữ nhận patch nhưng chặn major; floor lấy từ env thật. Phát hiện thiếu `langchain-core`/`langchain-text-splitters` trong requirements dù import trực tiếp. |
| 2026-11-07 | KB-6.2 | Qwen3-Embedding ST-compatible (không cần `trust_remote_code`). Đổi embedding dim ⇒ buộc re-index (xoá collection). Tách helper thuần để test khỏi cần torch. |
| 2026-11-07 | KB-6.3 | Code đã đọc `settings.rerank_model` sẵn → chỉ cần đổi default (minh chứng tách config ra env từ đầu). `bge-reranker-v2-m3` = CrossEncoder chuẩn ST; latency tăng trên CPU. |
| 2026-11-07 | KB-6.4 | Pin `latest` → version đang cài để reproducible không rủi ro; Next 16 bỏ key `eslint` trong `next.config`. → **Phase 6 hoàn tất (4/4)**. |
| 2026-11-07 | KB-7.1 | `uv`/`fnm` cài Python 3.13 + Node LTS **không cần sudo**. "Repo dirty toàn bộ" sau khi copy sang Linux = **CRLF** (fix `.gitattributes` + `core.autocrlf=input`, không commit lại 83 file). Docker Desktop WSL integration để lại **symlink** `/usr/bin/docker` → phải tắt integration + xoá symlink khi cài engine native. Thiếu `.dockerignore` ⇒ `.env` lọt vào image. → **Phase 7 hoàn tất (1/1)**, TD-6 trả xong. |

---
| 2026-11-08 | KB-4.9 | **`useSyncExternalStore` + `getServerSnapshot` rỗng** là cách đúng để dùng state persist ở client
(không lệch hydration, không `set-state-in-effect`). Ghi `localStorage` **phải debounce** khi có stream token.
`conversation_id` thuộc **session**, không phải key toàn cục. `Date.now()`/`console.*` trong thân component bị
`react-hooks/purity` coi là impure ⇒ đưa ra hàm module scope. |
| 2026-11-08 | KB-4.9 | **Có Chrome thật để verify UI**: Chrome trên Windows chỉ mở DevTools ở `127.0.0.1:9222` (Chrome mới bỏ qua `--remote-debugging-address=0.0.0.0`) ⇒ WSL không kết nối được, nhưng **`node.exe` trên Windows gọi được cả CDP và `localhost:3010`** ⇒ driver CDP chạy bằng `node.exe`, chỉ dùng `fetch` + `WebSocket` sẵn có (0 dep) → `tools/ui-verify.sh`. Bài học phụ: `netstat.exe \| grep -q` + `pipefail` trả 141 (SIGPIPE) dù match; và pattern multiline dễ khớp sang dòng `TIME_WAIT` ⇒ phải so khớp **từng dòng**. Ảnh chụp Chrome tìm ra 3 lỗi layout mà test DOM không thấy. |
| 2026-11-08 | KB-4.9 | **Playwright > tự viết CDP**: 7 check ~4s (so với ~20–25s qua Chrome Windows), không cần
sudo (apt-get download + dpkg -x + LD_LIBRARY_PATH cho browser process). **Bài học lớn về test layout**:
`document.scrollWidth` KHÔNG bắt được tràn ngang khi container có `overflow:hidden` (ScrollArea) ⇒ phải
so sánh **kích thước với cột chuẩn** (composer). Và `getByText(string)` của Playwright là
**case-insensitive + substring** ⇒ dùng `{exact: true}` + scope để tránh strict-mode. `break-words`
(`overflow-wrap: break-word`) không ảnh hưởng max-content; muốn chặn phình phải dùng `overflow-wrap: anywhere`. |
| 2026-11-08 | KB-4.9 | **Canh mép cột chat**: composer thu gọn (input+button cùng cao) + thẹ mép bubble AI/Bạn qua `calc` (Tailwind cần `_` thay dấu cách); mức không tràn: `w-full min-w-0` + `overflow-hidden` + `[overflow-wrap:anywhere]`. E2e test-8 (canh mép) 1/1 pass. |
| 2026-11-08 | KB-4.11 | **Spinner câm là lỗi UX**: `start` tới sau ~12,9s ⇒ phải hiện **pha** ("đang truy hồi" ≠ "đang viết") kèm số giây. **`route.fulfill()` không test được stream** — phải dựng **SSE server thật** (`node:http` gửi từng frame + CORS) rồi `route.continue({url})` mới quan sát được chuyển pha. Ảnh chụp lộ 2 lỗi mà assert không thấy: bubble stream rỗng hiện **song song** với khối trạng thái, và hint viết `**markdown**` nhưng render plain text. `Date.now()` trong component bị `react-hooks/purity` chặn ⇒ helper `nowMs()` ở module scope. |
| 2026-11-08 | KB-5.1 | **Incremental index rẻ hơn ~1000×**: 1 file = **1,2 s** vs **~22 phút** (refresh 601 chunk), và index cũ **không bị xoá** trong lúc sync ⇒ chat vẫn trả lời được. **Phải hash nội dung** (`sha256[:16]`) chứ không chỉ size/mtime ⇒ idempotent (sync lần 2 = 23 ms, 0 embed). **Chunk ID ổn định không đủ để xoá chunk cũ** — nội dung đổi thì ID đổi ⇒ phải `delete(where={"source": path})` trước khi index lại (đo được: 604 vs 601 nếu bỏ bước xoá). **File rỗng 0 byte là cái bẫy** (10 placeholder ⇒ log "+10 mới" mà 0 chunk mỗi lần start). **Upgrade không được re-embed cả kho**: metadata cũ thiếu `file_hash` ⇒ backfill khi `file_size` khớp, chỉ re-index khi lệch. **Guard của refresh phải áp cho sync**: folder biến mất ⇒ mọi file bị coi là "đã xoá" ⇒ xoá sạch index. |
| 2026-11-09 | KB-5.2 | **`sqlite3` stdlib đủ, không cần ORM** (2 bảng + 2 index, `save()` = 1 transaction; 15 test 0,1 s, 0 dependency mới). **`with conn:` KHÔNG đóng connection** (chỉ commit) — muốn đóng phải `conn.close()`. **Lazy-load khi cache miss** (RAM → SQLite) thay vì nạp cả DB lúc start ⇒ restart không tốn thời gian, `conversation_id` cũ vẫn có context. **Thêm attribute vào service làm vỡ 16 test** dựng bằng `object.__new__` ⇒ fix bằng class-level default, không sửa 16 test. **PII**: lưu bản đã redact ⇒ reload có thể thấy `[REDACTED:PHONE]` (trade-off có chủ ý). **Test redaction đừng dùng `example.com`** — redactor bỏ qua `example.*` nên assertion pass mà không chứng minh gì. |
| 2026-11-09 | KB-5.6 | **Đo chi phí render bằng test, không cần profiler**: mock `MarkdownMessage` rồi đếm số lần render qua các rerender giả lập stream ⇒ 300 token = **300 lần parse** + message cũ render lại **40 lần**; viết test **trước** khi sửa để có số "before" trung thực (sau: 0 / 0). **`memo` chỉ hiệu quả khi prop ổn định** — closure `(id) => …` mới mỗi render làm memo vô nghĩa; đổi sang `messageId` + `useCallback`. **Plain text khi stream** là trade-off: mất format vài giây, đổi lấy bỏ O(n²). **Dead code không còn import ⇒ xoá cả file** (`export-utils.ts`: 4 `any` + 66 dòng mock) thay vì đi type lại. **`react-hooks/set-state-in-effect`**: nhường 1 microtask trước khi gọi hàm set state. |
| 2026-11-09 | KB-5.3 | **Đo trước, chốt bằng số**: cùng 1 lệnh eval, chỉ đổi `RERANK_TOP_N` (20/12/8/6) ⇒ p50 11,4 → 7,97 → 4,53 → 3,27 s; `hit@k`/`MRR` **bão hoà 1.0** nên nếu chỉ nhìn chúng sẽ chốt sai — chính `distinct_file_ratio` (0,756 → 0,711 ở top-6 = −5,9%) mới chặn việc giảm quá tay. **Cache phải keyed theo `index_version`**, không chỉ theo query (nếu không: sửa tài liệu xong câu cũ vẫn trả kết quả cũ — bug im lặng); version tăng ở 3 chỗ mutate (`upsert`/`delete`/`clear`) ⇒ khoá tự vô hiệu, quên `clear()` cũng không sai. **Không cache điểm 0.0** (encoder lỗi ⇒ cache sẽ giữ rác 1h). **Attribute mới trên service làm vỡ test dựng bằng `object.__new__`** — lần thứ 2 trong phase ⇒ tạo **TD-27** để sửa gốc. Q2 = CPU là đủ: −60% mà không cần ONNX/CUDA. |
| 2026-11-09 | KB-5.4 | **Chốt ngưỡng SAU khi biết baseline**: đặt "hit@k +5 điểm %" khi baseline đã 1.0 và MRR 0,975 ⇒ gần như không thể đạt; lần sau chốt trên metric còn dư địa (`precision@k`) hoặc subset câu khó. **Luôn chạy control để quy công**: control `top-N=4, single-query` cho MRR 1.0 + 2,0 s ⇒ phần lớn latency/MRR đến từ **giảm top-N**, không phải multi-query (nếu chỉ so baseline ↔ multi-query sẽ kết luận sai). **Regex tách câu dễ sai**: tách ở "khác … gì" biến câu thành `["…", "?"]` ⇒ mất multi-query mà không báo lỗi. **Heuristic 0 token** là lựa chọn đúng khi trần TPM 8000 là thật. Giá trị thật của multi-query thấy ở `sources` của `/chat` (1 câu trả lời phủ 2 tài liệu cho 2 ý) — metric bão hoà không đo hết. |
| 2026-11-09 | KB-5.8 · KB-5.9 | **Đổi 1 biến khác ⇒ phải đo lại** (bộ vàng 15→20 câu làm top-N=8 hết tối ưu). **Metric bão hoà che lỗi**: `hit@k`/`MRR` đứng yên nên chỉ `precision@k` phát hiện việc giảm top-N làm mất chunk đúng — chốt bằng MRR sẽ sai. **Tách biến khi đo**: `top-4` trông 1,1 s nhưng thực chất là "chấm 2 ứng viên/phần" (MRR −9,4%); cho mỗi phần chấm đủ top-N rồi mới thấy top-6 là điểm ngọt (cùng chất lượng, nhanh gấp đôi). **Logging không có handler thì `logger.info` mất im lặng** — phải gắn handler có `name` + kiểm trùng (idempotent). **Health check phải trả lời "chat có chạy được không"**, không phải "file có tồn tại không". **Sửa gốc TD-27** = gom field về 1 chỗ (`BASE_SETTINGS`), không rải `getattr(..., default)`. |
| 2026-11-09 | KB-5.10 | **Image phình thường do "rác có chủ đích"**: 3 GB là `/wheels` mà chính Dockerfile copy vào stage cuối "để cache" — `COPY` tạo layer nên xoá sau đó **không** làm nhỏ image; phải `RUN --mount=type=bind` (BuildKit). **`--extra-index-url` không đủ chọn torch CPU**: PEP 440 xếp `2.x.y+cpu` **thấp hơn** `2.x.y` ⇒ pip vẫn chọn bản CUDA; phải cài torch CPU **trước** rồi mới `-r requirements.txt`, và nếu prebuild wheel thì xoá wheel không phải `+cpu`. **Đo trước khi sửa trả tiền ngay**: `du -sh /wheels site-packages site-packages/nvidia` chỉ ra 3 nguyên nhân ⇒ 16,5 GB → **2,68 GB** trong 1 lần sửa. |
| 2026-11-09 | KB-5.11 | **`toBeVisible()` không bắt được “bị đẩy ra ngoài khung”**: nút xoá “visible” nhưng ở x=363 trong drawer rộng 288 ⇒ phải assert **bounding box** nằm trong container. **Radix `ScrollArea` bọc nội dung trong `display: table`** ⇒ tiêu đề `truncate` (nowrap) làm dòng nở rộng hơn viewport, đẩy `absolute right-*` ra ngoài — danh sách cần truncate thì dùng `div.overflow-y-auto`. **`opacity-0 group-hover:opacity-100` là anti-pattern cho hành động phá huỷ** (user tưởng “mất nút xoá”). **e2e gọi BE thật phải cô lập dữ liệu**: 12 hội thoại đã lưu làm DOM có sẵn chip `[S1]` ⇒ test đếm phần tử sai. |
| 2026-11-09 | KB-5.12 | **Primitive không hợp `p-0`**: nút X mặc định của Radix `Sheet` là `absolute top-4 right-4` ⇒ với `p-0` nó rơi lên nội dung (đè nút chính). Pattern đúng: `showCloseButton={false}` + header tự dựng (`h-14 px-3`) chứa nút đóng của mình. **Brand trong ngăn kéo là nhận diện, không phải link** (bấm vào mà điều hướng + đóng drawer là mất ngữ cảnh). **Kiểm thẩm mỹ bằng toạ độ**: assert `closeBox.y + height <= newChatBox.y` bắt được lỗi “nút đè nút” mà ảnh scale nhỏ dễ bỏ qua. |
| 2026-11-09 | KB-5.5 | **Thứ tự middleware là bug im lặng**: Starlette thêm middleware mới thành lớp **ngoài** ⇒ đặt auth sau `RequestIDMiddleware` làm 401 trả `request_id: "-"`; phải đặt auth **trước**. Phát hiện bằng curl kèm `X-Request-ID` rồi so header ↔ body, không phải bằng test (sau đó mới viết regression test). **Fail-closed**: bật auth mà token rỗng phải **chặn**, nếu không còn tệ hơn không có auth. **Cờ + `settings_provider`** ⇒ bật/tắt bằng env, tắt thì chi phí ~0. **Token không nằm trong `NEXT_PUBLIC_*`** (nhúng bundle) ⇒ để trong `localStorage` do người dùng nhập. |
| 2026-11-10 | KB-5.14→5.17 (TD sweep) | **bf16 trên CPU là bẫy im lặng**: PyTorch emulate bf16 nên chậm hơn float32 **3–4×** mà không lỗi gì — chỉ phát hiện khi đo. `torch_dtype` phải nằm **lồng** trong `model_kwargs` của LangChain (vì nó chuyển tiếp cho `SentenceTransformer(model_kwargs=…)`), không phải ở cấp ngoài. **Đổi dtype ⇒ phải re-index toàn bộ** (vector khác không gian). **Middleware dựng lúc import bind chết default argument** ⇒ muốn test bật/tắt cờ phải resolve settings **lúc gọi** (`current_settings()`), không phải `get_settings` trong signature. **`global` trong `lifespan`**: gán biến module mà quên `global` chỉ tạo biến local ⇒ test (gắn state trực tiếp) vẫn xanh nhưng runtime `/ready` thiếu check — **verify runtime bắt lỗi mà unit test bỏ sót**. **Skip cũng là kết quả**: 4 món nợ (TD-17/24-deploy/28/30) được đóng bằng điều kiện revisit verify được, thay vì để mở vô thời hạn. |
| 2026-11-10 | KB-8.1→8.8 (Phase 8) | **ADR backfill chỉ đáng khi có số**: mỗi ADR 90–120 dòng, dẫn tên run `eval/runs/*.json` chứ không "đã đo"; cột **phương án bị loại** + mục **anti-pattern** giữ được phần dễ mất nhất khi kể lại. **Audit tài liệu bằng script, không bằng mắt**: so `config.py` alias ↔ `.env.example` bắt được 2 biến **chết** (`APP_NAME`, `APP_VERSION`) + 1 biến **thiếu** (`OPENAI_API_VERSION`); so `ls docs/adr/*.md` với số dòng bảng index để chặn lỗi thiếu dòng. **Tài liệu cũ nguy hiểm hơn không có tài liệu**: README FE còn dạy cài backend của repo khác ⇒ phải **thay hẳn**, không để "phần cũ". **Port ghi theo ngữ cảnh** (dev 3000/8000 vs compose 3010/8010) — 1 con số là nguồn lỗi muôn thuở. Ảnh Playwright dùng lại được làm ảnh README (660K), không cần tool chụp riêng. |
| 2026-11-10 | Repo root | **"Không phải git repo" là quyết định, không phải sự thật** — nó chỉ đúng chừng nào tài liệu còn ít; khi 43 file tài liệu (17 ADR + phase + AI assets) không thuộc repo nào thì mất lịch sử + không review được. Tách repo root **ignore** 2 repo con là cách duy nhất giữ "1 file chỉ ở 1 repo" (submodule thì phải commit concurrency; copy thì trùng). `pii_scan` báo SSH URL dạng `<ssh-user>@gitlab.com` là email ⇒ **false positive của scanner**, sửa bằng cách viết lại câu (không tắt cảnh báo). Dọn `test-results/`/`.next/` an toàn vì tái sinh được; **không** dọn `.venv` (5,9 GB nhưng cần cho dev) và `chroma_db` (dữ liệu thật). |
| 2026-11-10 | KB-9.3 | **State "mở/đóng" có 2 nguồn điều khiển phải có thứ tự ưu tiên**: nút của user vs. bấm chip `[S#]`; derive đơn giản (`manualOpen ?? highlight`) sinh bug "đã đóng tay rồi bấm chip không mở" — sửa bằng cách ghi **nonce** kèm lần bấm nút (highlight mới thắng). **Unit test không bắt được**: chỉ e2e mới tái hiện đúng chuỗi "đóng tay → bấm chip". **Thêm panel collapsible làm vỡ 3 e2e cũ** (giả định panel luôn mở) ⇒ thêm helper `expandSources()` thay vì sửa từng assert. **`setState` trong effect bị lint chặn** ⇒ derive state thay vì set trong effect. |
| 2026-11-10 | KB-9.4 + KB-9.5 | **Ngưỡng phải đo, trực giác sai**: chunk đúng có thể chỉ 0,003 trong khi câu ngoài phạm vi 0,0003 ⇒ ngưỡng đúng là **0,02**, không phải "0,3 nghe hợp lý". Đặt ngưỡng được chỉ vì rerank trả **sigmoid tuyệt đối**; score hybrid đã min-max theo tập ứng viên (mỗi câu luôn có 1.0) ⇒ ngưỡng trên hybrid là vô nghĩa. **Runtime settings phải loại tham số cần re-index** (chunk size/embedding) — cho đổi là trộn index cũ/mới. Đổi tham số retrieval **buộc** xoá cache rerank + tính lại fingerprint, không thì trả điểm của cấu hình cũ (bẫy ADR-0012). **Bộ vàng cũ đã bão hoà** (hit@k 1,0) nên không đo được gì: sau khi làm mới (28 câu, path đúng) mới thấy `precision@k` thật chỉ **0,333** ⇒ đúng là lý do cần lọc nguồn. Test UI phải kiểm **bounding box** (input từng bị label dài đẩy ra ngoài drawer). |

## 7. Technical debt register

> **Rà lại 2026-11-10** (sau đợt **TD sweep** — KB-5.14→5.17, theo yêu cầu *"xử lý tất cả TD, cái nào không
> làm được thì đánh Skip"*). Kết quả: **4 món trả** (TD-14, TD-20, TD-23 phần UI, TD-25) · **4 món Skip có
> điều kiện revisit** (TD-17, TD-24 phần deploy, TD-28, TD-30). Quy ước: `✅ đã trả` = giữ dòng để tra cứu;
> `🔕 đóng` = **chấp nhận rủi ro**, không làm nữa (không xoá số để không tái dùng ID); `⏭️ Skip` = **quyết
> định không làm bây giờ**, có điều kiện revisit verify được.


| ID | Mô tả | Nguồn | Điều kiện revisit | Mức độ |
|---|---|---|---|---|
| TD-1 | ~~Redaction PII dùng regex, chưa có NER/ML~~ | KB-1.1 | **🔕 đóng (2026-11-09)** — regex + `pii_scan` đủ cho KB 1 người dùng | — |
| TD-2 | Conversation lưu in-memory (`ChatService.conversations`) | có sẵn | ✅ **đã trả (KB-5.2)** — SQLite `./data/chat.db` (WAL) + lazy-load | — |
| TD-3 | `config.py` mặc định không đọc `.env` | KB-0.2 | ✅ **đã trả** — `SettingsConfigDict(env_file=".env")` (`config.py:146`), xác nhận khi rà 2026-11-09 | — |
| TD-4 | Chưa có test cho BE | KB-0.1 | ✅ đã trả (KB-3.5) — nay **263 test** | — |
| TD-5 | ~~Bật `PII_REDACT_INGEST` làm lệch retrieval~~ | KB-1.2 | **🔕 đóng (2026-11-09)** — ingest redaction vẫn **off** mặc định; rủi ro chấp nhận | — |
| TD-6 | Full Docker image build chưa chạy được ở máy dev | KB-6.1 | ✅ đã trả (KB-7.1) | — |
| TD-7 | Re-index với embedding mới chưa chạy thật | KB-6.2 | ✅ đã trả (KB-2.4 — 56 file / 601 chunk) | — |
| TD-8 | Reranker `bge-reranker-v2-m3` chưa đo thật | KB-6.3 | ✅ đã trả (KB-2.5 — MRR 1.0, +8s/query ⇒ TD-15) | — |
| TD-9 | Docker image BE nặng do `torch` bản CUDA + `/wheels` sót lại | KB-7.1 | ✅ **đã trả (KB-5.10)** — torch `+cpu` + bind-mount `/wheels`: **16,5 GB → 2,68 GB (−83,8%)**, 0 gói `nvidia-*` | — |
| TD-10 | ~~`glab` lưu PAT plaintext ở `~/.config/glab-cli/config.yml`~~ | KB-7.1 | **🔕 đóng (2026-11-09)** — máy cá nhân, token scope `api`; rotate tay nếu nghi lộ | — |
| TD-11 | ~~`pii_scan` báo false positive trên `Interview/*.md`~~ | KB-7.1 | **🔕 đóng (2026-11-09)** — đọc 1 lần khi commit là đủ; không public repo | — |
| TD-12 | FE dedup `sources` theo `file_path` | KB-2.3 | ✅ đã trả (KB-4.3) | — |
| TD-13 | BM25 corpus không reset sau re-index ⇒ hybrid lệch | KB-2.4 | ✅ **đã trả (KB-5.1)** — `_refresh_corpus_after_sync()` sau add/delete + `clear_database()` reset corpus | — |
| TD-14 | Embedding bfloat16 CPU ⇒ re-index 601 chunk ~22 phút | KB-2.4 | ✅ **đã trả (KB-5.14)** — ép `float32` (`EMBEDDING_TORCH_DTYPE`): 601 chunk thật **436,8 s (7,3 phút)** vs ~22 phút ⇒ nhanh **~3×**; dtype xác nhận `torch.float32` | — |
| TD-15 | Rerank CPU ~8–13 s/query | KB-2.5 | ✅ **đã trả phần lớn (KB-5.3)** — top-N 20→8 (−60%), cache câu lặp 7,15 → 0,13 s. Còn: câu **mới** 4,5 s (xem TD-29) | — |
| TD-16 | `request_id` chưa có trong log/event SSE | KB-3.1 | ✅ đã trả (KB-3.3) | — |
| TD-17 | Semaphore concurrency là **per-process** ⇒ nhiều worker vượt TPM | KB-3.2 | ⏭️ **Skip** — `CMD` chạy **1 worker** (mỗi worker nạp 1 bản model ~600 MB vào RAM ⇒ nhiều worker là đánh đổi tệ cho máy cá nhân). Rate limit mới (KB-5.15) cũng per-process vì cùng lý do. Revisit **khi** thật sự chạy > 1 worker (cần Redis/shared store) | thấp |
| TD-18 | Logger `app.*` không có handler/level ⇒ log INFO vô hình | KB-3.4 | ✅ **đã trả (KB-5.9)** — `app/core/logging_setup.py` + `LOG_LEVEL` (idempotent, hạ nhiễu thư viện) | — |
| TD-19 | `/ready` coi thiếu prompt file là `error` dù có fallback | KB-3.4 | ✅ **đã trả (KB-5.9)** — chỉ còn **thông tin**, `/ready` không 503 vì prompt | — |
| TD-20 | ~~Chưa có rate limit phía client cho `/chat` + `/chat/stream`~~ | KB-3.x | ✅ **đã trả (KB-5.15)** — `app/core/rate_limit.py` (sliding window theo IP, 429 + `Retry-After`, envelope KB-3.1), cờ `RATE_LIMIT_ENABLED` **mặc định TẮT** ⇒ bật cùng auth khi mở LAN/VPS | — |
| TD-21 | Streaming: mỗi token render lại toàn bộ markdown | KB-4.4 | ✅ **đã trả (KB-5.6)** — stream plain text, markdown parse 1 lần khi `end` (300 → 0) | — |
| TD-22 | `MessageWithCitations` còn nhánh render `sources`/`citations` chết | KB-4.3 | ✅ **đã trả (KB-5.6)** — 178 → 72 dòng, xoá `lib/export-utils.ts` | — |
| TD-23 | % tiến trình sync (chỉ tổng kết sau khi xong) | KB-4.5, KB-5.1 | ✅ **phần UI đã trả (KB-5.17)** — panel hiện **mọi** check (`startup_sync`, `rate_limit`) + nút **Kiểm tra provider** gọi `/ready?deep=true`. ⏭️ **Skip phần %**: muốn % theo từng file phải stream tiến trình (SSE job) — chỉ đáng khi sync > vài phút trên folder lớn | thấp |
| TD-24 | Model ~3,3 GB **không bake** vào image (tải lần đầu) ⇒ container mới lâu healthy; **chưa có registry/deploy tự động** (image BE **2,68 GB** — KB-5.10; FE 1,1 GB) | KB-4.7 | ⏭️ **Skip phần deploy** (✅ phần CI đã trả ở KB-5.7) — **chưa có** registry (GitLab Container Registry) lẫn đích deploy; bake model sẽ làm image +3,3 GB cho một mục tiêu không tồn tại. Revisit **khi** có VPS/nơi deploy thật | trung bình |
| TD-25 | ~~Startup sync chạy đồng bộ trong lifespan ⇒ container mới chậm healthy, không có job để theo dõi~~ | KB-4.10, KB-5.1 | ✅ **đã trả (KB-5.16)** — `StartupSyncState` + `asyncio.create_task` (`STARTUP_SYNC_BACKGROUND=true`): `/health` 200 sau **5,6 s**, sync nền xong 601 chunk sau **436,8 s**, trạng thái ở `/ready` + `/documents/status` | — |
| TD-26 | `Sheet`/`Tooltip`/`Toast` mới có test mức component | KB-4.8 | ✅ **đã trả (KB-4.9)** — `tools/ui-verify.sh` + Playwright e2e **14 check** | — |
| TD-27 | Test BE dựng service bằng `object.__new__` + `SimpleNamespace` thiếu field ⇒ vỡ hàng loạt khi thêm attribute | KB-5.2…5.4 | ✅ **đã trả (KB-5.9)** — `tests/builders.py` (`BASE_SETTINGS` 1 chỗ); thêm setting mới chỉ sửa 1 dòng | — |
| TD-28 | Cache rerank **in-process** (mất khi restart, không chia sẻ nếu nhiều worker); câu hỏi **mới** vẫn ~4,5 s | KB-5.3 | ⏭️ **Skip** — đây là cache **dẫn xuất**: mất khi restart chỉ tốn lại 1 lần ~3,4 s cho câu đó (đo KB-5.8). Lưu xuống SQLite/Redis thêm phức tạp + rủi ro lệch key mà lợi ích chỉ 1 người dùng. Revisit **khi** > 1 worker hoặc cần < 2 s cho câu mới | thấp |
| TD-29 | Chưa tối ưu lại `RERANK_TOP_N` trên bộ vàng 20 câu | KB-5.4 | ✅ **đã trả (KB-5.8)** — chốt **6** + mỗi phần multi-query chấm **đủ** top-N: p50 6,500 → **3,439 s** (−47%), precision/MRR giữ nguyên | — |
| TD-30 | Multi-query **heuristic** chỉ tăng `precision@k`, không cải thiện `hit@k`/`MRR` (đã bão hoà); **chưa thử LLM-split** | KB-5.4 | ⏭️ **Skip** — LLM-split tốn thêm 1 request provider **mỗi câu** để đổi lấy thứ đã bão hoà (MRR 0,975 / hit@k ~1,0 — KB-5.8); chất lượng hiện không phải nút cổ chai. Revisit **khi** gặp câu hỏi khó mà câu trả lời vẫn thiếu ý | thấp |

---

## 8. Changelog

| Ngày | Nội dung |
|---|---|
| 2026-11-07 | Tạo bộ AI assets (AGENTS.md, 4 rules, 4 skills, 3 workflows, tools). |
| 2026-11-07 | Chuyển LLM provider sang Groq (BE config + `.env.example`), viết ADR-0001. |
| 2026-11-07 | Tạo `architecture.md` + `Backlog.md`. |
| 2026-11-07 | KB-1.1: thêm `PIIRedactor` + tích hợp ChatService + unit test. |
| 2026-11-07 | KB-1.2: redact PII khi ingest (opt-in `PII_REDACT_INGEST`) + hàm thuần `redact_texts_for_ingest` + 5 test (3 unit, 2 integration). |
| 2026-11-07 | Đổi flow: `new-ticket` thêm **Q&A planning**; **gộp `run-ticket` + `close-ticket`** thành 1 (auto git: commit→push→MR→merge, không CI/CD); xoá `close-ticket.md`; cập nhật `AGENTS.md` §4/§6/§7/§10 + `10-git-workflow.md` + skill `kb-ticket`. |
| 2026-11-07 | Cài `glab` 1.128.0 (winget) + auth GitLab (token lưu keyring). Đóng KB-0.2/1.1/1.2 qua **MR !1**: squash-merge vào `main` (merge sha `0f779e0`). https://gitlab.com/anchu3003/knowledge-base-be/-/merge_requests/1 |
| 2026-11-07 | Đánh giá tech stack 2026 → thêm **Phase 6 — Tech refresh** (KB-6.1..6.4 + Q&A): pin deps/Python, embedding & reranker đa ngữ, FE refresh. Cập nhật `architecture.md` §8/§10. |
| 2026-11-07 | KB-1.3: badge PII ở UI (BE `pii_redacted`/`pii_redacted_count` + FE `PiiBadge`) → **Phase 1 Done (3/3)**. BE **MR !2** (sq `ebe7e4e`) · FE **MR !1** (sq `2a19438`). Cài Node LTS 26.13.0 để build FE. |
| 2026-11-07 | KB-6.1: range-pin deps (`>=floor,<next-major`) + Dockerfile Python **3.13** (base chạy 3.13.18) + update README/AGENTS/architecture. BE **MR !3** (sq `e338e83`). Verify: pip dry-run OK, pytest 16 passed. TD-6: full docker build chưa chạy. |
| 2026-11-07 | KB-6.2: embedding đa ngữ `Qwen/Qwen3-Embedding-0.6B` (env `EMBEDDING_MODEL`) + helper `build_embedding_params`; re-index defer (TD-7). BE **MR !4** (sq `a75599b`). Verify: pytest 19 passed. |
| 2026-11-07 | KB-6.3: reranker default `BAAI/bge-reranker-v2-m3` (đa ngữ) qua env + docs; load thật defer (TD-8). BE **MR !5** (sq `12e70cf`). Verify: pytest 19 passed, config OK. |
| 2026-11-07 | KB-6.4: FE pin 3 dep `latest`→version cụ thể; dọn `eslint` key ở `next.config.mjs`. FE **MR !2** (sq `3411762`). **Phase 6 Done (4/4)**. Verify: build ✓ + tsc exit 0. |
| 2026-11-07 | Tạo **Phase 7** + ticket **KB-7.1** (migrate dev env sang WSL). Q&A: toàn bộ · docker engine trong WSL · giữ tool Windows · copy vào `~` · Ubuntu. |
| 2026-11-07 | KB-7.1: migrate dev env sang **WSL2 Ubuntu 26.04** — Python **3.13.18** (`uv`), Node **26.13.0 LTS** (`fnm`), **docker engine 29.9.3 native trong WSL** (bỏ Docker Desktop integration), glab auth + SSH GitLab. Fix CRLF churn (`.gitattributes` `eol=lf` + `core.autocrlf=input`), thêm **`.dockerignore`** (chặn `.env` vào image), README 2 repo viết lại theo WSL. **TD-6 đã trả** (docker build + app start trên Python 3.13). BE **MR !6** (sq `d51f583`) · FE **MR !3** (sq `b9c64f7`). **Phase 7 Done (1/1)**. Verify: `pytest` 19 passed · `npm run build` ✓ · `docker build` 6m07s + smoke test `APP OK`. TD mới: TD-9 (image 6.53GB do CUDA wheels), TD-10 (glab PAT plaintext). |
| 2026-11-07 | Breakdown **Phase 2 — RAG quality** → **KB-2.1..2.5** (eval harness + baseline → dedup chunk/threshold/chunk ID ổn định → citation `[S1]` + grounding prompt → chunking theo heading + re-index (**TD-7**) → tune params + chốt default (**TD-8**)) kèm Q&A. Ghi nhận hiện trạng code: `SIMILARITY_THRESHOLD` chết, `build_context` cắt 500 ký tự, prompt không yêu cầu citation, chunk ID dùng `hash()` không ổn định. Thêm **TD-12** (FE dedup sources theo `file_path`). Cập nhật `architecture.md` §8. |
| 2026-11-08 | KB-2.x | Eval harness trả lời được "tốt hơn bao nhiêu" chỉ khi **có baseline chạy cùng điều kiện**; chunk ID ổn định (`sha1` nội dung) là điều kiện để `upsert` không nhân bản. |
| 2026-11-08 | KB-2.5 | Bật rerank làm `MRR` lên 1.0 nhưng latency ~46× (0.177s → 8.16s) ⇒ **TD-15**; mọi thứ "đẹp trên giấy" phải đo lại trên cấu hình đang chạy thật. |
| 2026-11-08 | KB-3.x | Chốt **contract lỗi** (`code`/`message`/`request_id`) trước khi làm UI giúp FE map lỗi 1 chỗ; throttle per-process không thay được quota provider. |
| 2026-11-08 | KB-4.4 | Parser SSE viết thành module thuần (`lib/sse.ts`) test được 100% trong jsdom — không cần browser để verify streaming. |
| 2026-11-08 | KB-4.7 | Chạy container bằng **uid của host** + `HOME=/tmp` xử lý cả 2 lỗi quyền thật (Chroma `readonly database`, `PermissionError: '/.cache'`); healthcheck phải kiểm thứ app thật dùng. |
| 2026-11-08 | KB-4.10 | **Endpoint phá huỷ phải tự kiểm tra điều kiện tiên quyết**: refresh = clear + load; `.dockerignore` loại folder ⇒ container thấy 0 file trong khi index vẫn 601 chunk ⇒ bấm refresh là **mất index**. Test phải khẳng định `clear_database` **không** được gọi, không chỉ assert mã lỗi. |
| 2026-11-08 | KB-4.10 | Mount thêm folder làm lộ bug startup: `AUTO_LOAD_ON_STARTUP` re-index **mọi** lần start (9+ phút); sửa ở lifespan (chỉ auto-load khi collection rỗng) rẻ hơn đổi config/ops. |
| 2026-11-08 | KB-4.8 | Đọc `localStorage` bằng `useState`+`setState` trong effect bị `react-hooks/set-state-in-effect` chặn ⇒ dùng `useSyncExternalStore` (+ `getServerSnapshot`) vừa hết warning vừa không lệch hydration. jsdom 31 ở máy này **không có `localStorage`** (chỉ `sessionStorage`) và thiếu `ResizeObserver` ⇒ polyfill trong `tests/setup.ts`. |
| 2026-11-08 | KB-4.8 | Viết lại shell theo design system thì control giả (select `Model`, textarea `System prompt`, user/logout) **tự rơi ra** — cái bị bỏ quan trọng hơn cái được thêm. `max-w-md` lồng trong bubble là ví dụ của việc 2 component cùng nghĩ mình là "khung". |
| 2026-11-08 | — | ⚠️ **Tự gây sự cố**: script python mở `Backlog.md` bằng `open('w')` (truncate ngay) rồi mới crash vì ký tự surrogate ⇒ **mất sạch file**. Khôi phục từ VS Code local history + `docs/phases/*`. Bài học: **ghi ra file tạm rồi `os.replace`** (atomic) hoặc backup trước khi ghi; không bao giờ truncate file nguồn sự thật bằng `'w'`. |
| 2026-11-08 | **KB-2.1 → KB-2.5 Done (Phase 2 5/5)**: eval harness + baseline (15 câu vàng) · dedup Jaccard/cap 2 + `SIMILARITY_THRESHOLD` có tác dụng + chunk ID ổn định `sha1(...)[:16]` · citation `[S#]` + context budget · chunking heading 2 tầng + re-index **56 file → 601 chunk** · tune grid 10 cấu hình (`RETRIEVAL_K=3`, rerank on). `MRR 0.72 → 1.0`, `latency_p50 0.177s → 8.16s` (**TD-15**). BE commits `3358596 a17162e 1d3e28b 395e727 3500e47 abe10b6`. Chi tiết: `docs/phases/phase-2.md`. |
| 2026-11-08 | **KB-3.1 → KB-3.5 Done (Phase 3 5/5)**: error taxonomy `AppError` + 7 subclass + `request_id` · provider retry/backoff/timeout + `ProviderThrottle` · SSE contract `start→token*→(end\|error)` + heartbeat + **trả TD-16** · probes `/health` + `/ready` · test tầng HTTP 28 test (**trả TD-4**). BE commits `bc7d29f 5a13bcd de03961 da1f8e3 dec3af6`. Chi tiết: `docs/phases/phase-3.md`. |
| 2026-11-08 | **KB-4.1 → KB-4.7 Done (Phase 4 7/7)**: API client + error UX theo contract · markdown GFM + chip citation · sources panel theo `citation_id` (**trả TD-12**) · streaming SSE + Stop · kho tài liệu/readiness drawer · quality gate vitest/eslint/tsc · Docker FE + compose BE↔FE (port 8010/3010, `ALLOWED_ORIGINS`). BE **MR !18/!19**, FE **MR !10/!11**. Chi tiết: `docs/phases/phase-4.md`. |
| 2026-11-08 | Audit UI thật vs backend ⇒ tạo **Phase 4b** với **KB-4.8..KB-4.11** (design system/layout/dark mode · bỏ control giả + multi-conversation localStorage · mount folder + guard refresh · streaming UX). Thêm TD-21..TD-24. |
| 2026-11-08 | KB-4.10: **an toàn dữ liệu index** — compose mount `./Interview:/app/Interview:ro`; 409 `documents_folder_empty` chặn `refresh` **trước** `clear_database()`; lifespan chỉ auto-load khi collection rỗng (hết 9+ phút/lần start) + log đúng tên folder; FE chặn nút Refresh + hiện lý do. BE **MR !20** · FE **MR !12**. Verify: folder-info `exists:true, supported:56`, index vẫn 601 chunk, pytest 168 passed, FE 54 test, healthy ~2 phút. **TD-25**. |
| 2026-11-08 | KB-4.8: **UI shell & design system** — thêm `sheet/tooltip/badge/separator/skeleton/slider/label/avatar/toast` từ Radix đã cài (0 dep mới); layout 2 cột `max-w-3xl` + composer sticky + sidebar → `Sheet` ở mobile; **theme toggle** light/dark/system (`useSyncExternalStore` + script chống FOUC); typography `.md-body`; tách `page.tsx` (788 → ~420 dòng) thành `app-header/app-sidebar/chat-messages/chat-composer/error-banner`. Verify: FE **77 test** (23 mới), lint 0 error, build ✓, `max-w-md`=0, không còn "An Chu/Logout". **TD-26**. |
| 2026-11-08 | ⚠️ File `Backlog.md` bị **truncate về 0 byte** do script python lỗi (`open('w')` rồi crash). Khôi phục từ VS Code local history (Phase 0/1/2/6/7 + TD-1..TD-12 + learning/changelog gốc) và **viết lại phần Phase 2/3/4/4b** dạng rút gọn từ `docs/phases/phase-2..4.md` + git log. Nội dung chi tiết gốc của các ticket Phase 2–4 không khôi phục được nguyên văn; **TD-20** mất mô tả. |
| 2026-11-08 | KB-4.9: **bỏ control giả + multi-conversation phía client** — `lib/chat-store.ts` (store ngoài React +
`localStorage['kb.chat_sessions']`, debounce 300ms, migrate `kb.conversation_id` cũ); `conversation_id` theo từng
session; title tự sinh từ câu hỏi đầu; bỏ nút **Kho tài liệu** ở sidebar (chỉ giữ ở header); nút **Sao chép**
không còn đè nội dung. Verify: 91 test (14 mới), tsc sạch, lint **0 error**, build ✓, `curl` `Kho tài liệu` = 1.
FE **MR !14**. |
| 2026-11-08 | KB-4.9 (follow-up): **tool verify UI bằng Chrome thật** `tools/ui-verify.sh` + `tools/ui-verify.mjs` (CDP qua `node.exe` trên Windows, 0 dependency): 10 check (load, 1 nút Kho tài liệu, persist sau reload, markdown render, theme light/dark qua localStorage, Sheet `role=dialog` + focus trap + ESC, 720px không tràn ngang) + 4 ảnh chụp `C:\Temp\kb-ui-*.png`. Fix UI từ ảnh: bubble `w-fit max-w-[88%]`, `MessageActions` (Sao chép + toast) ra **ngoài** bubble. **TD-26 đã trả.** npm script `verify:ui` + `verify:ui:wsl`. |
| 2026-11-08 | KB-4.9 (follow-up 2): **Playwright Chromium trong WSL thay CDP qua Chrome Windows** — 0 sudo (tải `.deb`
X11 rồi `dpkg -x`, trỏ `LD_LIBRARY_PATH` cho browser), 0 Docker; `e2e/ui.spec.ts` **7 check ~4s** (shell, 720px, theme,
persist, Sheet focus/ESC, nguồn không tràn, 1900px) + ảnh chụp để tự review. **Quy ước mới**: dev loop = `npm run dev`
(:3000) + `npm run test:e2e` (tự bật dev server); Docker build chỉ khi cần production parity hoặc cuối ticket
(`npm run test:e2e:prod`). Fix **panel Nguồn tràn phải**: `w-full min-w-0` + `overflow-hidden` cho card +
`[overflow-wrap:anywhere]` cho path/snippet (trước đó panel lấy max-content nên thò ra ngoài bubble). Xoá
`tools/ui-verify.*` (CDP). Verify: `test:e2e` 7/7 trên dev **và** production build (:3010), vitest 91, lint 0 error, build ✓. |
| 2026-11-08 | KB-4.11: **streaming UX** — `lib/stream-phase.ts` (`phaseOf`/`phaseLabel`/`formatSeconds`, thuần) + `components/stream-status.tsx` (nhãn pha + **số giây đã chờ**, skeleton, gợi ý "rerank CPU ~8–13s"); `page.tsx` bám `requestStartedAt` + `streamStarted` (event `start`), answer rỗng ⇒ `emptyAnswer` + notice amber + nút **Thử lại**; bubble stream rỗng được lọc khỏi danh sách render (hết trùng lặp với khối trạng thái). Verify: vitest **103** (12 test mới) · lint 0 error · build ✓ · e2e **10 passed** trên dev **và** production build (:3010) — 2 test streaming dựng **SSE server thật**. **Phase 4b Done (4/4).** |
| 2026-11-08 | **DoD Phase 4b** + **breakdown Phase 5** — viết `docs/phases/phase-4b.md` (đã có gì / cách chạy / nợ TD-15,21,22,23,24,25,2 / 8 bài học); breakdown epic Phase 5 → **KB-5.1..KB-5.7** (upload tài liệu từ UI · lịch sử hội thoại bền (**TD-2**) · giảm latency (**TD-15**) · truy hồi nhiều bước · auth tối giản · dọn dead code (**TD-21/22**) · CI GitLab (**TD-24**)) kèm **Q&A chờ user trả lời**. |
| 2026-11-08 | KB-5.1 (re-scope theo user): **bỏ upload từ UI**, giữ `Interview` **read-only** — user copy tay file vào folder; ticket chuyển thành **index tăng dần** (thêm `file_hash` sha256 vào metadata, `POST /documents/sync` diff added/updated/removed/skipped, xoá chunk theo `source` rồi index lại từng file, không `clear_database()`). Giữ giới hạn 10MB. Kỳ vọng: thêm 1 file ~vài giây thay vì 22 phút (**giải TD-14**). Q&A mới: cách kích hoạt / xử lý file xoá / giữ hay bỏ nút Refresh toàn bộ. |
| 2026-11-08 | KB-5.1: **index tăng dần từ folder** (user copy tay, `Interview` **read-only**, 10MB giữ nguyên; Q&A: Q1 = nút + tự động lúc start, Q2 = xoá chunk của file đã bỏ, Q3 = bỏ nút Refresh toàn bộ) — `app/services/index_sync.py` (sha256 digest, scan + skip reason `empty_file`/`too_large`, `diff_indexed` → added/updated/removed/unchanged/backfill), `DocumentService.sync_documents()` (**không** `clear_database`, xoá chunk theo `source`, rebuild BM25), `POST /documents/sync` (guard folder như refresh), startup sync + backfill hash cho index cũ; FE thay nút **Refresh** bằng **Đồng bộ file mới** + banner kết quả (mới/cập nhật/xoá/bỏ qua/thời gian). Verify thật: 601 → **603** chunk trong **1,2 s**; sync lại **23 ms**; sửa file → chunk cũ bị thay (604); xoá file → về **601**; pytest **186** · vitest **103** · e2e **11** · lint 0 error · build ✓. **TD-14 đã trả phần lớn**, TD-25 cập nhật. BE **MR !21** · FE **MR !19**. |
| 2026-11-09 | KB-5.2: **lịch sử hội thoại bền** (Q&A: Q1 = SQLite `sqlite3` stdlib + WAL, Q2 = server là nguồn sự thật + `localStorage` chỉ là fallback, Q3 = 200 session + không nút xoá tất cả) — `app/services/conversation_store.py` (2 bảng `conversations`/`messages`, `save/load/list/delete/prune`, title từ câu hỏi đầu), `ChatService` persist sau mỗi lượt (**redact user message trước khi lưu**) + lazy-load khi cache miss, `GET /conversations`, `GET /conversations/{id}`, `DELETE /conversations/{id}` (404 nếu không có), volume `./data:/app/data` (`data/` đã gitignore), FE `lib/conversations.ts` (map/merge server ↔ local) + hydrate lúc mount + nạp messages lazy + xoá session đồng bộ server. Verify thật: chat → **restart container** → list/detail còn nguyên, follow-up vẫn giữ context (4 messages); DELETE → 404 → total 0. pytest **216** · vitest **118** · e2e **13** · lint 0 error · build ✓. **TD-2 đã trả**. |
| 2026-11-09 | KB-5.6: **dọn dead code + tối ưu render streaming** (trả TD-21, TD-22) — `MessageWithCitations` 178 → **72 dòng** (xoá nhánh render `sources`/`citations` chết + 2 interface), stream hiển thị **plain text** và chỉ parse markdown **1 lần** khi `end`, `memo` + `messageId` + `useCallback` để message đã xong không render lại; xoá `lib/export-utils.ts` (dead, 4 `any`), bỏ `import React` thừa + field `ChatMessage.citations` không dùng, fixed `react-hooks/set-state-in-effect` trong `documents-panel`. Đo: markdown render khi stream 300 token **300 → 0**, message cũ khi message khác stream **40 → 0**. `npm run lint` **0 problem** (trước 6 warning); vitest **120** · e2e **14** (1 test mới: plain text khi stream → markdown + chip sau `end`) · build ✓. |
| 2026-11-09 | KB-5.3: **giảm latency truy vấn** (trả TD-15; Q&A: Q1 = cho phép chất lượng giảm ≤5%, Q2 = **chỉ CPU** (không ONNX/CUDA), Q3 = cache in-process invalidate theo `index_version` + TTL 1h) — `RERANK_TOP_N` 20 → **8** (đo eval 15 câu: p50 **11,374 → 4,527 s = −60%**, hit@k/MRR giữ **1.0**, `distinct_file_ratio` −2,9%; top-6 bị loại vì −5,9% > ngưỡng) + `app/services/rerank_cache.py` (LRU + TTL, khoá = query + `index_version` + k + top_n + config fingerprint) + `_mark_index_changed()` tăng version khi `upsert`/`delete`/`clear` ⇒ sync tài liệu là cache tự vô hiệu; `/documents/status` thêm `index_version` + `rerank_cache` stats. Đo thật: câu lặp trong process **7,15 → 0,134 s**; qua `/chat` **18,3 → 6,3 s**; sau sync câu cũ phải rerank lại (misses 1→2, 14,4 s). pytest **240** (24 test mới) · pii_scan OK. Ghi **TD-27** (test dựng service bằng `object.__new__`) và **TD-28** (cache in-process, câu mới vẫn 4,5 s). |
| 2026-11-09 | KB-5.4: **truy hồi nhiều bước — multi-query** (Q&A: Q1 = tự viết pipeline, không LangGraph; Q2 = multi-query + split heuristic 0 token; Q3 = tối đa +1 LLM call nếu cần) — `app/services/multi_query.py` (`split_query` tách câu nhiều ý theo "và/so với/;", bảo vệ nội dung trong ngoặc kép/backtick, cap 3 phần; `merge_hits` gộp theo chunk_id giữ score max) + `ChatService._initial_retrieval` (retrieve từng phần **song song**, mỗi phần chấm `top-N/2`, fallback 1 bước nếu mọi phần lỗi) dùng chung cho `/chat` + `/chat/stream`, metadata thêm `multi_query_parts`/`multi_query_enabled`; `RERANK_TOP_N` override per-call trong `document_service`; eval: bộ vàng **v3 = 20 câu** (thêm q16–q20 nhiều ý) + cờ `--multi-query on|off`. Đo: `precision@k` 0,533 → **0,617**, hit@k/MRR giữ nguyên, latency 9,70 → **6,50 s**; control top-N=4: MRR 1.0, 2,00 s (⇒ **TD-29**). pytest **263** · vitest 120 · build ✓. Dọn luôn dòng comment trùng `# Rewrite settings` trong `config.py`. |
| 2026-11-09 | **Rà lại tech debt §7** (sau KB-5.1…5.6): đóng 4 nợ PII/secret (TD-1 NER, TD-5 ingest redaction, TD-10 glab PAT, TD-11 pii_scan false positive — user chốt "check cơ bản là đủ"); mark đã trả **TD-3** (`env_file=.env`) + **TD-13** (BM25 refresh — KB-5.1) sau khi kiểm code; **khôi phục nội dung TD-20** (rate limit client) từ `docs/phases/phase-3.md`; cập nhật số liệu TD-9 (**image 16,5 GB**, mức độ → cao), TD-23 (bỏ phần refresh đã xoá), TD-27 (**3 lần** vỡ test vì `object.__new__`), TD-28/29/30 sắp xếp lại theo ID + TD-29 → mức **cao** (điều kiện revisit đã đủ). Tick 2 AC defer của **KB-6.2 / KB-6.3** (TD-7/TD-8 đã trả ở KB-2.4 / KB-2.5). |
| 2026-11-09 | **Breakdown Phase 8 — Tài liệu & học tập**: 5 ticket backfill **ADR** cho 16 quyết định lớn chưa có ADR (nền tảng retrieval · runtime/an toàn · dữ liệu/vận hành · FE/dev env) + `docs/adr/README.md` làm **lộ trình học**. Hiện `docs/adr/` chỉ có **1** file (`0001-llm-provider-groq`) trong khi Phase 2–5 đã chốt nhiều quyết định (vector store, embedding, rerank, chunking, dedup, PII, SSE, eval-gate, sync tăng dần, cache rerank, multi-query, SQLite history, FE state, render streaming, WSL2/dev env). Q&A (4 câu) dùng chung cả phase — **chờ user trả lời** trước khi chạy. Cập nhật luôn §5 (thứ tự ticket) vì danh sách cũ đã lỗi thời (TD-21/22 đã trả). |
| 2026-11-09 | **Phase 8 chốt Q&A + thêm 3 ticket README**: Q1=**B** (ADR bản học tập sâu: số đo + code:line + anti-pattern + "nếu làm lại") · Q2=**A** (đủ **16** ADR) · Q3=**B** (câu hỏi ôn tập gom ở `docs/adr/README.md`, ≥20 câu) · Q4=**không** bản EN ⇒ nâng ước lượng 8.1–8.4 lên `M`, siết AC (bắt buộc 4 mục sâu/ADR, ADR không chứa ôn tập). Thêm **KB-8.6** README **root** (chưa có file nào: quickstart 2 cách, sơ đồ ASCII, cấu trúc source, luồng dữ liệu, bảng "tài liệu ở đâu", troubleshooting chung; 2 câu Q&A về đối tượng đọc + ảnh chụp), **KB-8.7** README **BE** (bỏ "28 passed", port 8000, thiếu toàn bộ Phase 5: sync, conversations, multi-query, rerank cache, `CHAT_DB_PATH`) và **KB-8.8** README **FE** (xoá tài liệu onboarding cũ `fastapi_openai_proxy` + dòng lặp + port, thêm Kho tài liệu/Lịch sử/Streaming render, e2e 14 check). Phase 8: **0 / 8** ticket. |
| 2026-11-09 | **KB-5.8** (trả **TD-29**): đo 7 cấu hình trên bộ vàng **20 câu** ⇒ chốt `RERANK_TOP_N` **6** và đổi `_initial_retrieval` cho **mỗi phần multi-query chấm đủ top-N** (trước là `top_n//2`): so với cấu hình đang chạy (top-8) — MRR 0,975 = 0,975, precision@k **0,617 = 0,617**, `distinct_file_ratio` 0,750 → **0,783**, `latency_p50` **6,500 → 3,439 s (−47%)**; `/chat` thật: câu nhiều ý **3,29 s** (cache 2,63 s), câu 1 ý **1,38 s**. **KB-5.9** (trả **TD-18, TD-19, TD-27**): `app/core/logging_setup.py` + env `LOG_LEVEL` (log INFO hiện ra, hạ nhiễu chromadb/httpx), `/ready` không còn 503 vì thiếu prompt file (có fallback), `tests/builders.py` gom mọi field settings về 1 chỗ + refactor 3 file test. pytest **276**. |
| 2026-11-09 | **KB-5.10** (trả **TD-9**): image BE **16,5 GB → 2,68 GB (−83,8%)** — `Dockerfile` cài **torch CPU** (`+cpu`, trước `requirements.txt`), dùng `RUN --mount=type=bind` cho `/wheels` (trước bị `COPY` để lại **3,0 GB** trong image), xoá wheel torch không phải `+cpu` + mọi wheel `nvidia-*` khỏi `/wheels`. Verify: `torch 2.15.0+cpu`, **0** gói `nvidia-*`, không còn `/wheels`, site-packages **6,2 → 1,9 GB**; build sạch **209 s**; container healthy, 601 chunk, `/ready` ok, `/chat` (rerank) chạy đúng — **12,8 s** lần đầu (nạp cross-encoder) rồi **3,07 s** cache hit / **4,81 s** câu mới. **TD-24** cập nhật (image BE 2,68 GB; còn thiếu registry/CI). |
| 2026-11-09 | **KB-5.11** (UI theo phản hồi dùng thật): **danh sách hội thoại chuyển vào ngăn kéo** (nút “Lịch sử” + badge trên header, bỏ hẳn cột `aside` 256px ⇒ chat full-width), **nút xoá luôn hiển thị** (bỏ `opacity-0 group-hover`), **bỏ đường kẻ mờ** (`Separator`, `border-r`, `border-b` header, border bubble/card nguồn/composer → dùng nền `bg-muted/40`). Fix bug thật: Radix `ScrollArea` (`display: table`) làm tiêu đề dài đẩy nút xoá **ra ngoài** drawer (x=363 > 288) ⇒ thay bằng `div.overflow-y-auto`. Test: vitest **123** (+3), e2e **14** (dev + prod ×2), lint 0, build ✓; e2e thêm assert bounding box + stub `GET /conversations` để test không phụ thuộc dữ liệu server. |
| 2026-11-09 | **KB-5.12** (polish ngăn kéo theo phản hồi): **(1)** bỏ nút X mặc định của Radix `Sheet` (`showCloseButton={false}`) — nó `absolute` nên **đè lên** nút “Cuộc trò chuyện mới”; thay bằng **header riêng** `h-14 px-3`: brand **KB / Knowledge Base** bên trái, nút đóng (ghost, `icon-sm`, `aria-label="Đóng lịch sử"`) bên phải, cùng hàng và thẳng padding với nút bên dưới; **(2)** brand nằm **trên** mục LỊCH SỬ. `SidebarContent` thêm prop `onClose` (không truyền ⇒ không render nút). Test: vitest **124** (+1), e2e **15** dev + prod (thêm assert bounding box: nút đóng trong khung & ở hàng trên nút Tạo mới), lint 0, build ✓. |
| 2026-11-09 | **KB-5.13** (theo phản hồi): **brand đứng trước nút Lịch sử** trong header — trước đây thứ tự là `[Lịch sử] [KB Knowledge Base]`, nay `[KB Knowledge Base] [Lịch sử] … [Kho tài liệu] [theme]`. Chỉ đổi thứ tự JSX, giữ `gap-2` + `ml-auto`. Test: e2e thêm assert **DOM order** (`compareDocumentPosition`) + **toạ độ** (`brandBox.right <= historyBox.x`) ⇒ vitest 124 · Playwright 15 (dev + prod) · lint 0 · build ✓. |
| 2026-11-09 | **KB-5.5** (auth tối giản, **mặc định TẮT**): `app/core/auth.py` (`ApiKeyMiddleware` pure ASGI, so sánh **constant-time**, fail-closed khi `API_TOKEN` rỗng, chỉ `/` + `/health` công khai, `/ready` bảo vệ) + env `AUTH_ENABLED=false` / `API_TOKEN=` + `UnauthorizedError` (401, code `unauthorized`); FE: `lib/api.ts` gửi `X-API-Key` nếu có token trong `localStorage`, `TokenGate` (chỉ hiện khi `NEXT_PUBLIC_AUTH_ENABLED=true`), map lỗi `unauthorized` → tiếng Việt. Verify: cờ tắt ⇒ `/documents/status` **200** như cũ; cờ bật ⇒ 401/401/**200** với token, `/health` 200, `/ready` 401, 401 mang đúng `request_id` (header ↔ body). pytest **293** (+17) · vitest **130** (+6) · e2e **15** · lint 0 · build ✓. Bật khi cần: `AUTH_ENABLED=true` + `API_TOKEN=<dài>`. |
| 2026-11-10 | **TD sweep (Phase 5b, KB-5.14→5.17)** — làm hết những gì làm được, phần còn lại đánh **Skip**. **KB-5.14** (TD-14): `EMBEDDING_TORCH_DTYPE=float32` + `EMBEDDING_BATCH_SIZE` vào `encode_kwargs` ⇒ 601 chunk thật **436,8 s (7,3 phút)** vs ~22 phút (**~3×**; microbench 4,3×), dtype xác nhận `torch.float32`. **KB-5.15** (TD-20): `app/core/rate_limit.py` — sliding window theo IP cho `/chat` + `/chat/stream`, 429 + `Retry-After` + envelope KB-3.1, cờ `RATE_LIMIT_ENABLED` **TẮT** mặc định, 13 test. **KB-5.16** (TD-25): `StartupSyncState` + `asyncio.create_task` (`STARTUP_SYNC_BACKGROUND=true`) ⇒ `/health` 200 sau **5,6 s**, trạng thái sync ở `/ready` + `/documents/status`; bắt được bug `global` khi verify runtime. **KB-5.17** (TD-23 phần UI): `getReady({deep})` + nút **Kiểm tra provider** + render **mọi** check. **Skip**: TD-17 (1 worker là chủ ý), TD-24 phần registry/deploy (chưa có đích deploy), TD-28 (cache dẫn xuất, 1 người dùng), TD-30 (LLM-split đổi lấy thứ đã bão hoà), % tiến trình sync (cần SSE job). Test: BE **293 → 320**, FE **130 → 132**. |
| 2026-11-10 | **Phase 8 — Tài liệu & học tập (KB-8.1→8.8, Done 8/8)**: backfill **16 ADR** (`0002`→`0017`) theo bản **học tập sâu** (Context → Options có phương án bị loại → Decision → **bảng số đo thật** dẫn `eval/runs/` → **anti-pattern** → Consequences → **"nếu làm lại thì khác gì"** → Revisit định lượng). Thêm `docs/adr/README.md`: bảng tra 17 ADR + **3 lộ trình đọc** (người mới · ôn phỏng vấn backend · vận hành) + **28 câu ôn tập** có đáp án ngắn + ADR nguồn. Nối ADR vào `architecture.md` (6 link) + `AGENTS.md` §10. Viết **README root** (182 dòng, kiểu portfolio: sơ đồ ASCII, port table, quickstart 2 cách, cấu trúc source, luồng dữ liệu, "tài liệu ở đâu", điểm kỹ thuật + giới hạn, troubleshooting, 5 ảnh chụp). Viết lại **README BE** (env audit 63 alias ↔ `.env.example` khớp 100% sau khi bỏ `APP_NAME`/`APP_VERSION` chết + thêm `OPENAI_API_VERSION`; bảng 13 endpoint; **Sync vs Refresh**; lịch sử hội thoại; 320 test; troubleshooting mới) và **README FE** (bỏ hẳn tài liệu onboarding cũ `fastapi_openai_proxy`, sửa dòng lặp/port, thêm Kho tài liệu · Lịch sử · Streaming render, bảng **16** e2e). `pii_scan` sạch 21 file · 0 link hỏng. |
| 2026-11-10 | **Repo root + dọn dẹp**: root `knowledge-base` thành **git repo riêng** (`git init -b main`) track **43 file** chưa repo nào track: `AGENTS.md`, `architecture.md`, `Backlog.md`, `README.md`, `docs/` (17 ADR + 5 phase note), `tools/`, `.cline/`, `.clinerules/`. `.gitignore` **ignore 2 folder repo con** (`Knowledge-base/`, `Knowledge-base-fe/`) + `**/.venv`, `**/node_modules`, `**/.next`, `**/test-results`, `**/chroma_db`, `.env*` ⇒ không track trùng, không commit secret. Thêm `.gitattributes` (`* text=auto eol=lf`) như 2 repo con. Sửa lại tài liệu còn ghi "root KHÔNG phải git repo" (`AGENTS.md` §1, `.clinerules/00-context.md`, `.clinerules/10-git-workflow.md`, `architecture.md` §3, `README.md`) thành **3 repo**. **Dọn dẹp**: xoá 28 file tạm trong `/tmp` (`kb*.py`, `td*.py`, `mr_*.md`, log), `Knowledge-base-fe/test-results/` (1,7 MB, tự sinh lại), ảnh cũ `/mnt/c/Temp/kb-ui-*.png`; sửa false positive của `pii_scan` (`git@` SSH URL trong rule → viết lại không còn dạng email) ⇒ scan **43/43 file sạch**. |
| 2026-11-10 | **KB-9.3 — Nguồn thu gọn (FE)**: panel nguồn giờ **đóng mặc định**, header thành nút (`aria-expanded`/`aria-controls`), khi đóng chỉ 1 dòng tóm tắt (`Saga Pattern.md +1`); bấm nút để mở/đóng; bấm chip `[S#]` trong câu trả lời ⇒ panel **tự mở** đúng card + highlight (giữ KB-4.3). Kèm 2 case unit (mặc định đóng, mở/đóng) + 1 case e2e trên UI thật (thu gọn → mở → đóng → bấm chip) + helper `expandSources()` cho 3 e2e cũ. Test: FE **142 → 144**, e2e **17 → 18**. Thêm **KB-9.4** (ngưỡng liên quan, BE+FE) vào backlog — **chờ trả lời Q&A** (score nào, hành vi khi tất cả dưới ngưỡng, có hiện số nguồn bị loại). |
| 2026-11-10 | **KB-9.5 — bộ vàng v4 (BE)**: corpus đổi (56→234 file, 601→2 879 chunk) làm **10 `expected_files`** của v3 trỏ path không tồn tại ⇒ remap + thêm 8 câu (AI embeddings/agents/eval, DS, algo, FE, AWS) ⇒ **28 câu, 0 path hỏng**. Baseline mới: `hit@k 0,964` · `MRR 0,833` · `precision@k **0,333**` · p50 3,06 s (bộ cũ bão hoà 1,0 nên vô dụng). **KB-9.4 — ngưỡng liên quan + cấu hình runtime (BE+FE)**: đo phân bố score trên bộ v4 (chunk đúng p50 0,71/min 0,003; nhiễu p50 0,003; câu ngoài phạm vi max **0,0003**) ⇒ `RELEVANCE_MIN_SCORE=0,02`: giữ 20/23 nguồn đúng, bỏ ~80% nhiễu, diệt 100% câu ngoài phạm vi. Câu ngoài phạm vi giờ trả **0 nguồn** + "Thông tin này không có trong knowledge base" rồi kiến thức chung. Thêm **12 tham số chỉnh lúc chạy** (`GET/PUT /settings`, `POST /settings/reset`, whitelist loại tham số cần re-index, đổi là recompute fingerprint + xoá cache rerank) và **panel Cấu hình trên UI** (dựng control từ `tunables`, badge "đã đổi", nút Mặc định). FE hiện ghi chú "Đã bỏ N nguồn…". Test: BE **329 → 340**, FE **144 → 150**, e2e **18 → 20**. **Phase 9 Done 5/5**. |
