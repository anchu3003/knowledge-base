# ADR-0007 — PII/secret redaction: che ở **cổng ra** (trước khi gửi LLM), mặc định BẬT

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) · TD-1 đóng có chủ ý |
| **Ngày** | 2026-11-07 (KB-1.1) · rà lại 2026-11-09 |
| **Liên quan** | KB-1.1, KB-1.2, KB-1.3, KB-5.2 (redact trước khi lưu) · `AGENTS.md` §9.5 · `.clinerules/30-pii-safety.md` · code: `app/services/pii_service.py` |

## Context

Đây là **knowledge base cá nhân**: tài liệu là ghi chú làm việc, có thể chứa email đồng nghiệp, số điện
thoại, mã đơn hàng, connection string, API key dán tạm. LLM (Groq) là **bên thứ ba** — đã gửi là không
rút lại được.

Ràng buộc thực tế:

- Không được làm hỏng chất lượng trả lời (che quá tay ⇒ câu trả lời vô nghĩa).
- Không được chặn ingest (người dùng vẫn muốn index tài liệu có email).
- 1 người dùng ⇒ không cần audit log/DLP phức tạp.

## Options

| Điểm đặt redaction | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Cổng ra**: câu hỏi + retrieved context + history, trước mỗi request LLM (chọn) | Chặn đúng chỗ rò rỉ; index giữ nguyên văn (retrieval không bị lệch); 1 chỗ duy nhất | Không bảo vệ dữ liệu đã nằm trong vector store/DB (nếu máy bị lấy) | ⭐ Cần retrieval chính xác + chặn rò ra ngoài |
| Cổng vào (redact khi ingest) | Dữ liệu trong DB sạch | **Lệch retrieval**: câu hỏi có email thật không khớp chunk đã che (đo ở KB-1.2) | Khi DB là nơi rủi ro nhất |
| Cả hai | An toàn nhất | Recall giảm + khó debug ("vì sao chunk này không khớp") | Khi có dữ liệu nhạy cảm thật |
| Không redact | Đơn giản | Vi phạm PII rule; không chấp nhận được | — |

Về **kỹ thuật nhận diện**: regex + placeholder (`[REDACTED:email]`) vs NER/ML.

## Decision

1. **Redact ở cổng ra, mặc định BẬT** (`ENABLE_PII_REDACTION=true`): áp cho câu hỏi user, context
   retrieved, history và cả prompt của query-rewrite.
2. **Ingest redaction TẮT** (`PII_REDACT_INGEST=false`) — vì nó làm lệch retrieval (KB-1.2): che email
   trong tài liệu thì câu hỏi chứa email thật không còn khớp.
3. Dùng **regex + placeholder theo loại** (email, sđt VN, CCCD, số TK, `sk-…`, `gsk_…`, JWT, private
   key, connection string), thay vì NER.
4. Redact **trước khi lưu** hội thoại vào SQLite (ADR-0014) ⇒ lịch sử không giữ bản thô.

## Bằng chứng (số đo thật)

| Kiểm chứng | Kết quả | Nguồn |
|---|---|---|
| Bộ test redaction | pass (`tests/test_pii_service.py`, `test_ingest_redaction.py`) | `pytest -q` → 320 passed |
| Ingest redaction làm lệch retrieval | có ⇒ tắt mặc định | KB-1.2 + `config.py:...PII_REDACT_INGEST` |
| Ảnh hưởng lên câu trả lời khi bật cổng ra | không đo được hồi quy trên bộ vàng (câu hỏi không chứa PII) | `eval/runs/*` |
| Quét trước commit | `python tools/pii_scan.py <files>` → `[OK] Không phát hiện PII/secret` | dùng ở mọi ticket |

**Giới hạn đã chấp nhận (TD-1 đóng 2026-11-09)**: regex **không** bắt được PII không theo mẫu (tên
người, địa chỉ viết tự do). User chốt *"check cơ bản là đủ"* cho KB 1 người dùng, không public repo.

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Chỉ redact `message` của user**: context retrieved cũng là nội dung tài liệu → rò PII y như vậy. Code
  phải redact **mọi** chuỗi đi vào prompt (đã gồm cả query-rewrite prompt).
- **Redact sau khi log**: log là nơi rò rỉ thứ hai; log chỉ được chứa `request_id`, code lỗi, số liệu —
  **không** nội dung thô (`middleware.py`, `chat_service.py` đều theo quy ước này).
- **Bật ingest redaction để "an toàn hơn"**: đo được là giảm recall; an toàn hơn nhưng trả lời kém hơn
  mà không ai nhận ra vì không có metric recall.

## Consequences

- **Được**: tài liệu có PII vẫn index được; nội dung gửi LLM đã che; 1 chỗ duy nhất dễ test.
- **Mất**: câu trả lời có thể chứa placeholder `[REDACTED:email]` nếu tài liệu nhắc tới email (trade-off
  có chủ ý — thà vậy còn hơn rò). Lịch sử reload cũng hiện placeholder (ADR-0014).
- **Tech debt**: TD-1 (regex thay NER) — **đóng**; TD-5 (ingest redaction off) — **đóng**.

## Nếu làm lại thì khác gì

1. Thêm **test chống rò rỉ ở tầng prompt**: assert rằng mọi chuỗi gửi provider đã qua `PIIRedactor`
   (hiện test theo từng service, dễ quên khi thêm luồng mới như multi-query rewrite).
2. Có **metric "số PII đã che/câu"** đẩy vào `/documents/status` (hiện chỉ log stats) để biết redaction
   có đang ăn vào tài liệu thật không.
3. Nếu sau này public repo/share dữ liệu: bật NER (spaCy/presidio) cho tiếng Việt + audit log.

## Revisit

Xem lại khi:

- Có **> 1 người dùng** hoặc đưa KB lên VPS public.
- Tài liệu chứa PII **có cấu trúc mới** (CCCD gắn chip, IBAN, mã số thuế) — thêm rule regex + test.
- Cần **chứng minh tuân thủ** (audit) ⇒ NER + log redaction (khi đó mở ticket riêng, không làm lén).
