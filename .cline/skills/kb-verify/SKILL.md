---
name: kb-verify
description: Verify một ticket Knowledge Base bằng lệnh thật (uvicorn, curl /chat, pytest, npm run build, ollama/llm thật) và dán output thật vào ticket. Dùng khi nghiệm thu ticket hoặc điền mục "Kết quả verify" trong Backlog.md.
---

# Verify ticket Knowledge Base

Nguyên tắc (`AGENTS.md` §4.4, §8, §9): **dán output thật**, không nói suông. Không claim "đã test" khi chưa chạy.

## Lệnh verify tham khảo

| Vùng | Lệnh | Kỳ vọng |
|---|---|---|
| BE — chạy app | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` (trong venv) | startup log OK, `http://localhost:8000/docs` mở được |
| BE — health | `curl http://localhost:8000/` | `200` |
| BE — chat | `curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{ "message": "..." }'` | JSON có `response` |
| BE — test | `pytest -q` | pass |
| FE — build | `npm run build` (trong `Knowledge-base-fe`) | build success |
| FE — dev | `npm run dev` | `http://localhost:3000` mở được |
| PII | `python tools/pii_scan.py <file>` | không phát hiện PII/secret |

> Lệnh chính xác lấy theo `README.md` và ticket — skill chỉ gợi ý.

## Quy trình

1. Xác định lệnh verify từ Acceptance Criteria của ticket.
2. Chạy lệnh, copy **output thật** (không tóm tắt mơ hồ).
3. Nếu fail → ghi rõ fail ở đâu, **không** đánh dấu Done.
4. Điền vào mục **Kết quả verify**: `lệnh đã chạy + output tóm tắt`.
5. Không chạy được (thiếu môi trường) → nói rõ lý do, chuyển ticket sang `Blocked`.

## Không được làm

- ❌ Ghi "đã test, chạy tốt" mà không có output.
- ❌ Đánh dấu `Done` khi chưa chạy verify thật.
- ❌ Dán PII/secret thô vào ticket khi ghi output — che trước (`sk-REDACTED`, `user@example.com`).
