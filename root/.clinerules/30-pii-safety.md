# 30 — PII & secret safety (bắt buộc)

Rule behavioral. Đây là **rule nhạy cảm nhất** của dự án: đây là **knowledge base cá nhân**, tài liệu
làm việc + ghi chú cá nhân → rất dễ chứa **thông tin cá nhân (PII)** và **secret**. LLM là **bên thứ ba**
(Groq / Gemini / …) → **không được gửi thẳng PII lên đó** khi chưa che.

## 1. Ranh giới dữ liệu

| Loại | Ví dụ | Bắt buộc |
|---|---|---|
| **PII** | email cá nhân, số điện thoại, CCCD/CMND, số tài khoản, địa chỉ nhà, ngày sinh | Redact trước khi gửi LLM |
| **Secret** | mật khẩu, `sk-…`, `gsk_…`, JWT, private key, connection string, OTP | Redact **và** không bao giờ commit |
| **Nội dung công khai/kỹ thuật** | code, doc, kiến thức | Gửi bình thường |

## 2. Bắt buộc trong CODE

- **Mọi** request gửi tới LLM phải đi qua lớp redaction (`app/services/pii_service.py`).
  Áp dụng cho: câu hỏi user, retrieved context (tài liệu), history, và cả prompt của query-rewrite.
- Redaction là **mặc định BẬT** (`ENABLE_PII_REDACTION=true`); tắt phải có lý do + ghi tech debt.
- **Log không được** chứa PII/secret thô: không `logger.info(message)` khi chưa redact.
- API key **chỉ** đọc từ env. Không hard-code.

## 3. Bắt buộc khi commit / tạo file

- `.env` **không** commit; chỉ commit `.env.example` với placeholder.
- Trước khi commit: chạy `python tools/pii_scan.py <files>` trên file đã sửa.
- Nghi ngờ lộ key → **rotate key ngay** (không chỉ xoá commit — git history vẫn còn).

## 4. Bắt buộc khi AI agent làm việc (Cline)

- Trả lời cho user có thể **hiển thị** PII trong **ngữ cảnh local**, nhưng **không** dán PII thô vào
  ví dụ minh hoạ, ticket, doc, hay bất kỳ nội dung sẽ gửi ra dịch vụ ngoài.
- Khi viết example: dùng dữ liệu giả (`user@example.com`, `09xx xxx xxx`, `sk-REDACTED`).
- Không echo lại `.env` / key trong chat.
- Khi user dán nội dung nghi chứa PII/secret → **cảnh báo** và đề xuất redact.

## 5. Thứ tự ưu tiên

Vi phạm PII/secret = **bug nghiêm trọng** (P0), xử lý **trước** mọi ticket feature.

## Liên quan

- Skill `.cline/skills/kb-pii-redaction` · Tool `tools/pii_scan.py` · `AGENTS.md` §9.5
