# ADR-0009 — Hợp đồng streaming SSE: `start → token* → (end | error)` + heartbeat

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-08 |
| **Liên quan** | KB-3.3, KB-3.4, KB-4.11 (pha truy hồi), KB-5.6 (render) · `architecture.md` §4 · code: `app/core/sse.py`, `app/main.py` (`/chat/stream`), `chat_service.py:288` (`stream_chat`) |

## Context

Câu trả lời mất 3–8 s (rerank + provider). Nếu chờ rồi trả 1 lần, user tưởng app treo. Cần stream, nhưng
stream có 3 cái bẫy thật:

1. **Proxy/nginx buffer** ⇒ token đến một cục, mất tác dụng streaming.
2. **Idle timeout**: khoảng lặng > 30–60 s (provider chậm, rerank 3–4 s) ⇒ proxy đóng kết nối.
3. **Client ngắt giữa chừng** (F5, đổi hội thoại): nếu không dọn, task provider tiếp tục chạy và **mất**
   phần câu trả lời đã sinh.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **SSE qua `StreamingResponse` + event có schema** (chọn) | đơn giản nhất, chạy trên HTTP/1.1, tự reconnect bằng `fetch` + `ReadableStream`; debug bằng `curl -N` | 1 chiều; không có kênh điều khiển | ⭐ Trả lời 1 chiều |
| WebSocket | 2 chiều, có ping/pong sẵn | Handshake/upgrade phức tạp, cần state, khó debug hơn, FE phải giữ socket | Cần interrupt/cancel giữa lúc stream |
| Poll `/chat/{id}/status` | Không cần streaming hạ tầng | Trễ, tốn request, phải lưu buffer ở server | Hạ tầng chặn SSE |
| Trả 1 lần (không stream) | Đơn giản nhất | UX tệ với 3–8 s | Batch/script |

## Decision

- Event schema: `start` (kèm `conversation_id`) → `token` (nhiều) → `end` (kèm sources, metadata) **hoặc**
  `error` (`{code, message, request_id}` — cùng envelope ADR-0008).
- **Heartbeat**: nếu quá `SSE_HEARTBEAT_SECONDS=15` không có event ⇒ gửi comment `: ping` (SSE comment
  không bị client hiểu là event nhưng vẫn làm mới kết nối).
- **Chống buffer**: header `X-Accel-Buffering: no` + `Cache-Control: no-cache`.
- **Client ngắt** ⇒ generator dừng sạch và **lưu phần câu trả lời đã sinh** vào hội thoại.
- Có thêm event pha (`phase`) để UI hiện "Đang truy hồi tài liệu" vs "Đang viết" (KB-4.11).

## Sơ đồ

```
client                    FastAPI (/chat/stream)                 service
  │  POST (message)             │                                   │
  │────────────────────────────>│                                   │
  │                             │── start {conversation_id} ───────>│ retrieve + rerank (3-4 s)
  │<── event: start ────────────│                                   │
  │                             │        (quá 15 s không token)     │
  │<── : ping ──────────────────│  ← heartbeat giữ kết nối          │
  │<── event: token (×N) ───────│<── token ─────────────────────────│ provider stream
  │<── event: end {sources} ────│<── end ───────────────────────────│
  │                             │                                   │
  │  (user bấm đổi hội thoại ⇒ đóng kết nối)                        │
  │──── X ─────────────────────>│ generator bị cancel               │
  │                             │── lưu partial answer ────────────>│ SQLite (redacted)
```

## Bảng: client ngắt giữa chừng thì chuyện gì xảy ra

| Thời điểm ngắt | Server làm gì | Dữ liệu còn lại | Rủi ro |
|---|---|---|---|
| Trước `start` (đang rerank) | Hủy generator, không gọi provider | Không có message | Không tốn quota |
| Giữa lúc stream token | Hủy generator, đóng kết nối provider | Câu trả lời **một phần** được lưu | Câu trả lời cụt (đúng ý user) |
| Ngay sau `end` | Không ảnh hưởng | Đầy đủ | Không |
| Mất mạng phía client | Như "giữa lúc stream" | Một phần | Không biết đã lưu gì cho tới khi mở lại |

## Bằng chứng (số đo thật)

| Kiểm chứng | Kết quả | Nguồn |
|---|---|---|
| Test stream (thứ tự event, heartbeat, disconnect) | pass (`tests/test_sse_stream.py`, `test_api_stream.py`, `test_chat_history_persistence.py`) | `pytest -q` → 320 passed |
| FE render streaming | plain text khi stream, markdown 1 lần khi `end` (ADR-0016) | `tests/stream-render.test.tsx` |
| `request_id` có trong event `error` | verified | `sse.py:39` (`error_event`) |

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Bọc `StreamingResponse` trong middleware thường** (BaseHTTPMiddleware): middleware đọc hết body trước
  khi trả ⇒ **mất streaming**. Vì vậy `RequestIDMiddleware`/`ApiKeyMiddleware`/`RateLimitMiddleware` đều
  viết **pure ASGI** (không buffer).
- **Heartbeat bằng task riêng đọc chung iterator**: bug đã gặp — mỗi lần heartbeat lại "giết" generator
  của service. Cách đúng: 1 task `pump()` bơm event vào queue, main loop chỉ đọc queue + timeout.
- **Không set `X-Accel-Buffering: no`**: sau nginx, user thấy "treo 5 s rồi hiện cả câu" — tưởng stream
  hỏng.
- **Không lưu partial**: user F5 giữa lúc stream ⇒ mất sạch câu trả lời đã đọc được.

## Consequences

- **Được**: UX thấy tiến trình; proxy an toàn (heartbeat + header); ngắt giữa chừng không mất dữ liệu;
  debug bằng `curl -N` dễ.
- **Mất**: SSE chỉ 1 chiều (muốn "stop generating" phải đóng kết nối — FE đang làm vậy); mỗi kết nối giữ
  1 slot semaphore khi đang gọi provider.
- **Tech debt**: chưa có test tự động cho "ngắt ở đúng ranh giới `start`" (test hiện cover ngắt giữa
  stream); chưa có metric đếm số lần heartbeat/những lần stream fail.

## Nếu làm lại thì khác gì

1. Đặt **version cho event schema** (`start` có `"v": 1`) ngay từ đầu — thêm `phase` (KB-4.11) đã phải sửa
   cả 2 phía, có version sẽ dễ tương thích ngược.
2. Viết test **property-based** cho thứ tự event (`start` luôn đầu, tối đa 1 `end|error`) thay vì test
   từng kịch bản.
3. Thêm endpoint `DELETE /chat/stream/{id}` để stop chủ động (hiện phải đóng kết nối từ FE).

## Revisit

Xem lại khi:

- Cần **stop/hủy chủ động** hoặc chỉnh sửa câu trả lời giữa lúc stream (→ WebSocket).
- Đặt sau reverse proxy có idle timeout **< 15 s** (phải giảm `SSE_HEARTBEAT_SECONDS`).
- Có **> 1 client** đồng thời (SSE giữ connection dài; cần kiểm tra giới hạn của uvicorn/proxy).
