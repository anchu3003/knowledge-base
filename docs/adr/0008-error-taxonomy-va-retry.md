# ADR-0008 — Hợp đồng lỗi (`AppError`) + một cổng gọi provider (semaphore + retry có ngân sách)

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) · TD-17 mở có chủ ý |
| **Ngày** | 2026-11-08 |
| **Liên quan** | KB-3.1, KB-3.2, KB-5.5 (auth dùng lại envelope), KB-5.15 (rate limit dùng lại), TD-17 · `architecture.md` §4 · code: `app/core/errors.py`, `app/core/provider_retry.py:100`, `app/main.py:196-250` |

## Context

Trước KB-3.1, mỗi endpoint tự ném `HTTPException` với message khác nhau; FE phải đoán lỗi bằng cách so
chuỗi ⇒ không phân biệt được "hết quota provider" (chờ rồi thử lại) với "sai body" (sửa request) hay
"provider chết" (báo user). Đồng thời Groq free tier có **TPM/RPM hữu hạn**: 2 request song song dễ ăn
`429`, còn retry mù (mỗi tầng tự retry) thì đốt quota gấp nhiều lần.

## Options

| Vấn đề | Phương án | Ưu | Nhược | Chọn |
|---|---|---|---|---|
| Định dạng lỗi | `HTTPException` rải rác | quen thuộc | FE phải parse message; dễ rò chi tiết nội bộ | ✗ |
| | **`AppError` + handler toàn cục** | 1 envelope `{error:{code,message,request_id}}`; code ổn định để FE switch | phải nhớ raise đúng subclass | ✓ |
| Chống vượt TPM | Không giới hạn | đơn giản | 429 liên tục trên free tier | ✗ |
| | **Semaphore `PROVIDER_MAX_CONCURRENCY=1`** | không bao giờ vượt TPM; 1 user thì không mất gì | chậm hơn khi có nhiều câu song song | ✓ |
| Retry | Retry ở mọi tầng | "chắc chắn thành công" | nhân số lần gọi (2 tầng = 4 lần), backoff mù, bỏ qua `Retry-After` | ✗ |
| | **1 cổng `ProviderThrottle` + retry có ngân sách** | 1 nơi duy nhất; đọc `Retry-After`; jitter | phải đi qua cổng này ở mọi call site | ✓ |

## Decision

1. **`AppError` (và subclass) là cách duy nhất báo lỗi nghiệp vụ**; handler ở `main.py` serialize thành
   `{"error": {"code", "message", "request_id"}}`, `request_id` lấy từ middleware.
2. Chi tiết nội bộ (`str(e)`, host provider, path) **chỉ vào log**; response chỉ có message chung.
3. **`ProviderThrottle` là cổng duy nhất** gọi provider: `asyncio.Semaphore(PROVIDER_MAX_CONCURRENCY=1)`
   + retry `PROVIDER_MAX_RETRIES=2`, backoff exponential + **equal jitter** (`PROVIDER_RETRY_BASE_DELAY=2`),
   ưu tiên header `Retry-After` của provider nếu có.
4. `map_provider_error()` map exception SDK → `AppError` (kiểm subclass trước: timeout ⊂ connection ⊂ api).

## Bảng ánh xạ lỗi → HTTP → code (khớp `app/core/errors.py`)

| Class | `http_status` | `code` | Khi nào |
|---|---|---|---|
| `ProviderAuthError` | 502 | `provider_auth_failed` | Provider từ chối key của mình |
| `ProviderRateLimitError` | 429 | `provider_rate_limited` | Hết quota/TPM phía provider |
| `ProviderUnavailableError` | 503 | `provider_unavailable` | Không gọi được provider |
| `ProviderTimeoutError` | 504 | `provider_timeout` | Provider không trả lời kịp |
| `DocumentStoreError` | 500 | `document_store_error` | Chroma/IO lỗi khi thao tác tài liệu |
| `DocumentsFolderEmptyError` | 409 | `documents_folder_empty` | Folder rỗng ⇒ chặn clear/sync (KB-4.10) |
| `ConversationStoreError` | 500 | `conversation_store_error` | SQLite lỗi |
| `UnauthorizedError` | 401 | `unauthorized` | Thiếu/sai `X-API-Key` (KB-5.5) |
| `RateLimitedError`* | 429 | `rate_limited` | Rate limit của **chúng ta** (KB-5.15, dựng trong middleware) |
| `NotFoundError` | 404 | `not_found` | Không thấy resource |
| `ServiceUnavailableError` | 503 | `service_unavailable` | Dependency chưa init |
| `AppError` (fallback) | 500 | `internal_error` | Lỗi không phân loại |

\* middleware rate limit dựng response trực tiếp (pure ASGI) nhưng dùng **cùng** `error_body()` + code
`rate_limited` ⇒ FE chỉ cần switch 1 bộ code.

## Bằng chứng (số đo thật)

| Kiểm chứng | Kết quả | Nguồn |
|---|---|---|
| Test contract lỗi | pass (`tests/test_error_contract.py`, `test_api_errors.py`, `test_provider_retry.py`) | `pytest -q` → 320 passed |
| 429 có `request_id` + `Retry-After` | verified (`tests/test_rate_limit.py`) | KB-5.15 |
| Retry không nhân đôi | 1 cổng `ProviderThrottle.session()`; rewrite prompt **không** retry (chỉ qua semaphore) | `chat_service.py:525` comment |

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Raise `HTTPException` trong service**: handler toàn cục không bắt được ⇒ response lệch schema, FE nhận
  `{"detail": ...}` và hiện "Unknown error".
- **Để retry ở cả service lẫn SDK**: `PROVIDER_MAX_RETRIES=2` × retry nội bộ SDK = 4 lần gọi cho 1 câu ⇒
  đốt quota free tier trong 1 buổi ôn tập.
- **`Semaphore` > 1 với free tier**: TPM tính theo phút; 2 câu song song mỗi câu 1.500 token dễ vượt
  trần ⇒ user thấy 429 dù "chỉ hỏi 2 câu".
- **Trả `str(exception)` cho client**: rò base URL, tên model, đôi khi cả key trong message của SDK.

## Consequences

- **Được**: FE map lỗi chính xác (retry vs sửa request vs báo lỗi); log có `request_id` xuyên suốt;
  không vượt TPM.
- **Mất**: mọi call provider phải đi qua `ProviderThrottle` (nếu ai gọi trực tiếp `llm.ainvoke` là vượt
  luật ngầm); `PROVIDER_MAX_CONCURRENCY=1` làm câu hỏi song song bị xếp hàng (chấp nhận với 1 user).
- **Tech debt**: **TD-17** — semaphore là **per-process**; rate limit (KB-5.15) cũng vậy ⇒ nhiều worker
  thì mức phạt thực tế = `limit × số worker`. Skip vì luôn chạy 1 worker.

## Nếu làm lại thì khác gì

1. Gộp `AppError` + handler vào 1 module `app/core/http_errors.py` kèm **test tự động so bảng** ở trên
   (hiện bảng là tài liệu tay, dễ lệch khi thêm class).
2. Thêm **metric đếm `429 provider`** vào `/documents/status` (hiện chỉ log) để biết mình có đang chạm
   trần TPM không.
3. Viết `ProviderThrottle` ngay từ Phase 0 — trước KB-3.2 code gọi provider ở 3 chỗ, mỗi chỗ tự retry.

## Revisit

Xem lại khi:

- Cần chạy **> 1 uvicorn worker** (khi đó semaphore/rate limit per-process không còn đúng → TD-17).
- Vượt **1.000 req/ngày** hoặc `provider_rate_limited` xuất hiện **> 5 lần/tuần** trong log.
- Thêm provider thứ hai (fallback) — lúc đó "cổng duy nhất" phải hỗ trợ chọn provider.
