# Phase 3 — Backend robustness (Done 2026-11-08)

> Mục tiêu phase: BE không còn "lỗi gì cũng 500 kèm `str(e)`". Contract rõ ràng cho lỗi, SSE, gọi provider,
> probe — và **có test ở tầng HTTP** để contract không âm thầm vỡ. Nguyên tắc: *contract là hợp đồng,
> test là thứ giữ hợp đồng*.

## Đã có gì sau phase

| Ticket | Kết quả |
|---|---|
| KB-3.1 | **Error taxonomy** `app/core/errors.py`: `AppError` + 7 subclass (`provider_auth_failed` 502, `provider_rate_limited` 429, `provider_unavailable` 503, `provider_timeout` 504, `document_store_error` 500, `not_found` 404, `service_unavailable` 503); 4 exception handler trong `main.py` ⇒ mọi lỗi là `{"error": {code, message, request_id}}`; middleware pure-ASGI cấp `X-Request-ID` (sanitize id client); xoá toàn bộ `detail=f"...{str(e)}"` |
| KB-3.2 | **Provider resilience** `app/core/provider_retry.py`: `ProviderThrottle` = semaphore (`PROVIDER_MAX_CONCURRENCY=1`) + retry có ngân sách (`PROVIDER_MAX_RETRIES=2`, base 2s, equal jitter, tôn trọng `Retry-After` giây/ms); `ChatOpenAI(timeout=…, max_retries=0)` ⇒ service là tầng retry duy nhất; stream chỉ retry trước token đầu |
| KB-3.3 | **SSE ổn định** `app/core/sse.py`: contract `start → token* → (end \| error)`, event `error` cùng schema `/chat` + `request_id`, heartbeat `: ping` (`SSE_HEARTBEAT_SECONDS=15`), header `X-Accel-Buffering: no` / `Cache-Control: no-cache`; disconnect lưu partial answer (`interrupted: true`), log `info` không stack |
| KB-3.4 | **Probes**: `GET /health` (liveness, luôn 200, `uptime_seconds`) + `GET /ready` (`provider_config` / `prompt_file` / `collection` ⇒ `ok` 200 · `degraded` 200 · `error` 503) + `?deep=true` gọi provider 1 request `max_tokens=1` (mặc định tắt); `Dockerfile` có `HEALTHCHECK curl /health` |
| KB-3.5 | **Test tầng HTTP** (`tests/conftest.py` + `test_api_endpoints.py` + `test_api_errors.py` + `test_api_stream.py`, **28 test**, chạy 0.13s); phát hiện + **fix bug thật** ở `GET /documents/folder-info` (`NameError: settings` — endpoint này trước đó luôn 500 khi có file); **trả TD-4** |

## Cách chạy ở thời điểm này

```bash
cd Knowledge-base

# Test toàn bộ (offline, ~1s) — 164 passed
.venv/bin/python -m pytest -q

# Chỉ test tầng HTTP (nhanh nhất, không cần model/Chroma)
.venv/bin/python -m pytest tests/test_api_endpoints.py tests/test_api_errors.py tests/test_api_stream.py -q

# Chạy app
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Probes (rẻ; deep=true mới tốn 1 request provider)
curl -s localhost:8000/health
curl -s localhost:8000/ready
curl -s "localhost:8000/ready?deep=true"

# Docker (HEALTHCHECK có sẵn trong image)
docker build -t kb-be:local . && docker run --rm -p 8000:8000 -e AUTO_LOAD_ON_STARTUP=false kb-be:local
```

## Contract chốt trong phase

| Contract | Nội dung |
|---|---|
| Error envelope | `{"error": {"code", "message", "request_id"}}` cho **mọi** lỗi HTTP; `code` là hằng số, message chung, không hint |
| Request id | header `X-Request-ID` (client gửi id hợp lệ `[A-Za-z0-9._-]{1,64}` thì giữ, else uuid4) — có trong header, body lỗi, và log |
| Provider | retry tối đa 2 lần cho `429`/`5xx`/timeout/connection; `4xx` khác fail ngay; concurrency 1 (TPM 8000); hết ngân sách → 429/504/503 |
| SSE | `start → token* → (end \| error)`; lỗi giữa stream = event `error` (HTTP vẫn 200); heartbeat `: ping`; disconnect sạch |
| Probes | `/health` không phụ thuộc gì; `/ready` 3 check rẻ + `deep=true` (tắt mặc định, **không** dùng trong HEALTHCHECK) |

## Cái gì CHƯA có (đừng tưởng đã có)

- **Chưa có CI/CD** ⇒ test chỉ chạy khi mình chạy tay; không có pipeline chặn merge.
- **Chưa có logging config**: logger `app.*` không có handler/level ⇒ log `info` (request_id mỗi request, disconnect)
  **không hiện** khi chạy uvicorn mặc định (chỉ WARNING+ thấy) — **TD-18**.
- **Concurrency limit là per-process**: chạy nhiều uvicorn worker thì mỗi process một semaphore ⇒ vẫn có thể vượt
  TPM — **TD-17**.
- **Chưa có metrics/observability** (Prometheus, tracing); chỉ logging + `request_id`.
- **Rerank vẫn ~8s/query trên CPU** (TD-15) ⇒ `/chat` chậm dù provider đã được retry/pacing đúng.
- **Rate limit phía client** (per-user/per-IP) chưa có — sẽ cân nhắc ở Phase 4/5.
- `?deep=true` chỉ kiểm **1 request** provider; không kiểm được quota còn lại của ngày.
- Không test `lifespan` khởi tạo thật (nặng): nếu lifespan vỡ, test HTTP vẫn xanh ⇒ phải verify bằng chạy app thật.

## Bài học của phase

1. **Thứ tự `isinstance` khi map lỗi SDK là bug tiềm ẩn**: `APITimeoutError ⊂ APIConnectionError ⊂ APIError` —
   check `APIError` trước thì timeout thành 503, bug chỉ lộ khi provider treo thật.
2. **Bỏ `try/except` ở endpoint mới là sửa bug gốc**: `except Exception → HTTPException(500, detail=str(e))`
   không phải "an toàn" mà là tầng **làm mất phân loại lỗi**.
3. **`asyncio.wait_for(anext(gen))` là bẫy** cho heartbeat SSE: timeout cancel `__anext__` ⇒ giết generator mỗi nhịp.
   Dùng task bơm event + queue.
4. **Disconnect có 2 dạng** (`CancelledError` khi client đóng, `GeneratorExit` khi `aclose()`); phải bắt cả hai,
   **re-raise**, và `finally` của generator phải **await** task đã cancel (nếu không, test disconnect xanh giả).
5. **Quota là tài nguyên thật**: healthcheck 30s × `deep=true` = 2 880 request/ngày > free tier ⇒ probe tự động
   **không bao giờ** được chạm provider.
6. **"Có cấu hình" ≠ "key đúng"**: 3 check rẻ không phát hiện key hết hạn — phải nói rõ giới hạn thay vì để
   người đọc tin `ok` là mọi thứ hoàn hảo.
7. **Test tầng HTTP trả công ngay lập tức**: viết test cho `/documents/folder-info` là phát hiện endpoint này
   **luôn 500** (`NameError: settings`) — 164 test unit trước đó không hề biết. Đây là lý do TD-4 phải trả.
8. **Verify bằng "provider chết"** (`OPENAI_BASE_URL=127.0.0.1:9`) cho hành vi retry/backoff/semaphore y hệt
   lỗi 429 thật, không tốn quota.

## Nợ kỹ thuật sau phase

| TD | Nội dung | Trạng thái |
|---|---|---|
| TD-4 | Chưa có test cho BE | ✅ **đã trả (KB-3.5)** — 164 test, trong đó 28 test tầng HTTP |
| TD-16 | `request_id` chưa có trong log/event của generator SSE | ✅ **đã trả (KB-3.3)** — truyền `request_id` vào `stream_chat()` |
| TD-17 | Semaphore per-process ⇒ nhiều worker vẫn vượt TPM | mở (thấp) |
| TD-18 | Logger `app.*` chưa có handler/level ⇒ log INFO vô hình | mở (thấp) |
| TD-19 | `/ready` coi thiếu prompt file là `error` dù `ChatService` có fallback prompt | mở (thấp) |

Các nợ cũ vẫn mở và **không** thuộc phase này: TD-1 (PII regex), TD-2 (history in-memory), TD-5 (ingest redaction),
TD-9 (image 6.53GB), TD-10 (glab PAT plaintext), TD-11 (pii_scan false positive), TD-12 (FE sources panel),
TD-14 (embedding dtype), TD-15 (rerank ~8s/query).
