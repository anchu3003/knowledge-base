# ADR-0014 — Lịch sử hội thoại: SQLite stdlib + WAL, redact trước khi lưu

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-09 |
| **Liên quan** | KB-5.2, KB-4.9 (localStorage), ADR-0007 (PII) · `architecture.md` §4 · code: `app/services/conversation_store.py`, `app/main.py` (`/conversations*`) · `CHAT_DB_PATH=./data/chat.db`, `MAX_CONVERSATIONS=200` |

## Context

Trước KB-5.2, `ChatService.conversations` là **dict trong RAM** ⇒ restart container là **mất sạch** lịch
sử. FE có `localStorage` (KB-4.9) nhưng đó là cache của **một** browser: đổi máy / xoá cache / dùng private
window là mất.

Ràng buộc: 1 người dùng, không muốn thêm Postgres/Redis (AGENTS.md §3.4); và **không** được lưu PII thô
xuống đĩa (ADR-0007).

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **`sqlite3` stdlib + WAL, 1 file trong `./data`** (chọn) | 0 dependency, 0 container; WAL cho đọc trong lúc ghi; backup = copy 1 file | single-writer; không có query phức tạp | ⭐ 1 user, 1 process |
| Postgres | mạnh, nhiều client | thêm container + volume + migration ⇒ phí | Nhiều service/user |
| Redis | nhanh | mất dữ liệu nếu không cấu hình persist; không phải nơi lưu "sự thật" | Cache/session ngắn hạn |
| JSON file | đơn giản nhất | ghi đồng thời dễ hỏng file; không index; file phình | < 10 hội thoại |

## Decision

1. `ConversationStore` trên `sqlite3` (**stdlib**), `PRAGMA journal_mode=WAL` + `busy_timeout` ⇒ đọc không
   bị chặn khi ghi, không hỏng file khi container bị kill.
2. **Server là nguồn sự thật**; FE `localStorage` chỉ là cache/fallback (KB-4.9 + KB-5.2: máy khác vẫn thấy
   hội thoại qua `GET /conversations`).
3. **Redact trước khi lưu** (dùng `PIIRedactor`) ⇒ DB không giữ PII thô.
4. Giới hạn `MAX_CONVERSATIONS=200` (xoá session cũ nhất khi vượt) để file không phình vô hạn.
5. Lazy-load: `GET /conversations` trả list metadata; `GET /conversations/{id}` mới trả messages.
6. DB không mở được ⇒ **vẫn chạy** (chat in-memory) thay vì chặn startup.

## Bằng chứng (số đo thật)

| Kiểm chứng | Kết quả | Nguồn |
|---|---|---|
| Test store + API + persistence | pass (`test_conversation_store.py`, `test_conversations_api.py`, `test_chat_history_persistence.py`) | `pytest -q` → 320 passed |
| Sống qua restart container | `Conversation store ready: ./data/chat.db (1 session đã lưu, max=200)` | log container sau rebuild KB-5.14 |
| Redact trước khi lưu | có test riêng cho placeholder trong messages | `test_chat_history_persistence.py` |
| FE fallback khi BE tắt | e2e "BE tắt (mọi endpoint lỗi) ⇒ vẫn dùng lịch sử localStorage" | Playwright 16/16 |

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Lưu PII thô rồi mới redact khi gửi LLM**: file `chat.db` trên đĩa là bản ghi vĩnh viễn — trái rule PII
  (ADR-0007). Redact **trước khi lưu** mới đúng.
- **Ghi từng token vào DB trong lúc stream**: 300 lần ghi/câu ⇒ I/O nặng + file WAL phình. Đúng: ghi **1
  lần** khi xong (hoặc khi client ngắt — ADR-0009).
- **Không có giới hạn số session**: `data/chat.db` phình mãi; với 1 user thì 200 session là quá đủ.
- **Chặn startup khi DB lỗi** (quyền ghi, volume thiếu): user mất cả chat, dù chỉ mất lịch sử.

## Consequences

- **Được**: lịch sử sống qua restart và qua nhiều browser; backup 1 file; không thêm hạ tầng.
- **Mất**: nội dung **đã che** ⇒ reload hội thoại cũ có thể thấy `[REDACTED:email]` (trade-off có chủ ý).
  Single-writer ⇒ không chạy 2 process cùng ghi (giống Chroma, ADR-0002).
- **Tech debt**: `data/` phải tồn tại & ghi được (xem Troubleshooting README BE); chưa có export/import
  hội thoại; chưa có dọn theo tuổi (chỉ theo số lượng).

## Nếu làm lại thì khác gì

1. Lưu **`redaction_stats`** mỗi message (số PII đã che) để biết tài liệu/hội thoại nào nhạy cảm.
2. Thêm **FTS5** để tìm trong lịch sử (`GET /conversations?q=`) — SQLite có sẵn, gần như miễn phí.
3. Đặt DB ở `CHAT_DB_PATH` với **migration version** (`PRAGMA user_version`) ngay từ đầu thay vì
   `CREATE TABLE IF NOT EXISTS` (đổi schema sau này sẽ phải tự xử).

## Revisit

Xem lại khi:

- Cần **tìm kiếm/xuất** lịch sử, hoặc chia sẻ hội thoại.
- Số session chạm **200** thường xuyên (tăng giới hạn hoặc dọn theo tuổi).
- Cần **> 1 process** ghi (→ Postgres, cùng lúc với TD-17).
