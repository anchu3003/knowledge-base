---
name: kb-pii-redaction
description: Triển khai, mở rộng và verify lớp redaction PII/secret trước khi gửi dữ liệu lên LLM (Groq/Gemini/...). Dùng khi thêm/sửa pattern, khi tích hợp redaction vào luồng chat/ingest, hoặc khi rà soát rò rỉ PII.
---

# PII / secret redaction cho Knowledge Base

Đây là **knowledge base cá nhân** → tài liệu có thể chứa PII/secret. LLM là bên thứ ba → phải che
trước (`AGENTS.md` §9.5, `.clinerules/30-pii-safety.md`).

## Kiến trúc

- Module: `Knowledge-base/app/services/pii_service.py` → class `PIIRedactor`.
- Áp dụng tại **cổng ra tới LLM** trong `chat_service.py` (message, context, history, rewrite).
- Tuỳ chọn áp dụng tại **ingest** trong `document_service.py` (ẩn PII trong chunk index) — bật/tắt bằng env.
- Config: `ENABLE_PII_REDACTION`, `PII_REDACT_INGEST`, `PII_PLACEHOLDER`.

## Loại dữ liệu phải che

| Nhóm | Ví dụ | Ghi chú |
|---|---|---|
| Email | `a.b@x.com` | cho phép domain ví dụ khi viết doc |
| Số điện thoại VN | `09xxxxxxxx`, `+84…` | |
| CCCD/CMND | 9–12 chữ số | |
| Số tài khoản/thẻ | 8–19 chữ số (ngữ cảnh) | tránh false-positive với số thường |
| Secret/key | `sk-`, `gsk_`, `ghp_`, JWT, PEM key | luôn che |
| Mật khẩu | `password=…`, `pwd: …` | che giá trị |
| Địa chỉ nhà / ngày sinh | tự do | heuristic, ghi tech debt nếu chưa làm |

## Nguyên tắc

- Redact = **thay bằng placeholder** (`[REDACTED:EMAIL]`), giữ cấu trúc câu để retrieval/LLM vẫn hiểu.
- Ưu tiên **precision**: tránh che nhầm số liệu kỹ thuật (port, token count, version `1.2.3`).
- Regex là lớp đầu — **ghi tech debt** cho NER/ML-based khi cần độ chính xác cao hơn.
- Có **unit test** cho từng pattern + case âm (số, version… không bị che).

## Verify

```bash
cd Knowledge-base
pytest -q tests/test_pii_service.py
python tools/pii_scan.py .
```

- Test phải khẳng định: input chứa email/sđt/key → output có placeholder, **không còn** giá trị gốc.
- Không dán PII thật vào test — dùng dữ liệu giả.
