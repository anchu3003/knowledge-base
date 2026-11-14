# ADR-0015 — State FE: store ngoài React + `useSyncExternalStore`, không Zustand/Redux

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-09 |
| **Liên quan** | KB-4.9, KB-5.2 (server là nguồn sự thật), KB-5.6 · `architecture.md` §5 · code: `lib/chat-store.ts`, `app/page.tsx` |

## Context

FE cần 3 thứ state: (1) danh sách hội thoại + messages (**persist** qua F5), (2) hội thoại đang chọn,
(3) trạng thái stream. Trước KB-4.9 chỉ có 1 `conversation_id` toàn cục trong `localStorage` ⇒ không có
multi-conversation, F5 mất nội dung.

Ràng buộc: Next.js **App Router** (server components + hydration), 1 user, không muốn thêm dependency
state nặng.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Store module-level + `useSyncExternalStore` + `localStorage`** (chọn) | 0 dependency; hydration-safe (`getServerSnapshot` trả rỗng); debounce ghi; test được bằng vitest | phải tự viết subscribe/serialize; không có devtools | ⭐ 1 loại state, ít component |
| Zustand | API gọn, persist middleware | thêm dependency; vẫn phải tự xử hydration mismatch với SSR | Nhiều store/selector |
| Redux Toolkit | Mạnh, devtools, chuẩn team | boilerplate lớn cho 1 user; bundle to hơn | Nhiều state phức tạp, nhiều dev |
| React Query (TanStack) | Chuẩn cho server state (cache/fetch/retry) | chỉ giải quyết server state, **không** giải quyết "messages đang stream" | Nhiều endpoint cần cache |
| `useState` trong `page.tsx` | đơn giản nhất | F5 mất, không chia sẻ giữa component (drawer cần đọc) | Prototype |

## Decision

- `lib/chat-store.ts`: **store ngoài React** (module-level snapshot + listener set), đọc bằng
  `useSyncExternalStore(getChatStoreSnapshot, getChatStoreServerSnapshot)`.
  - `getServerSnapshot` trả snapshot **rỗng/ổn định** ⇒ SSR và lần render đầu khớp nhau (không hydration
    mismatch), dữ liệu thật nạp ở effect.
- Persist `localStorage` (`kb.chat.v2`), **debounce 300 ms** khi đang stream ⇒ 300 token không tạo 300 lần
  ghi.
- **Server là nguồn sự thật** (KB-5.2): khi mở app, thử `GET /conversations`; lỗi/timeout ⇒ dùng
  `localStorage` (fallback) chứ không trắng màn hình.

## Bằng chứng (số đo thật)

| Kiểm chứng | Kết quả | Nguồn |
|---|---|---|
| Test store (parse/serialize/derive title/multi-conversation) | pass | `tests/chat-store` + `tests/conversations.test.ts` |
| Hydration an toàn | e2e không có warning mismatch; F5 vẫn thấy hội thoại | Playwright "F5 vẫn thấy hội thoại" |
| BE tắt hoàn toàn | vẫn dùng được lịch sử `localStorage` | Playwright "BE tắt (mọi endpoint lỗi)" |
| Máy khác (localStorage rỗng) | nạp hội thoại từ server | Playwright "máy khác vẫn thấy hội thoại" |
| Bundle | không thêm dependency state nào | `package.json` |

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Đọc `localStorage` trong `useState` initializer**: server render ra rỗng, client render ra có dữ liệu ⇒
  **hydration mismatch** (React log lỗi, UI nháy). Đúng: `getServerSnapshot` rỗng + nạp ở effect.
- **Ghi `localStorage` mỗi token**: main thread bận serialize 300 lần/câu ⇒ stream giật. Phải debounce.
- **Coi `localStorage` là nguồn sự thật**: 2 browser khác nhau sẽ lệch nhau; server mới là sự thật
  (ADR-0014). `localStorage` chỉ để mở app nhanh và chịu lỗi mạng.
- **Đưa toàn bộ messages vào Context**: mỗi token làm re-render cả cây ⇒ trùng vấn đề ADR-0016.

## Consequences

- **Được**: 0 dependency; F5 không mất; nhiều hội thoại; chịu được BE tắt; test được không cần browser
  thật (vitest) và có e2e cho hành vi thật.
- **Mất**: tự viết plumbing (~70 dòng), không có devtools; nếu state phức tạp lên (undo, sync nhiều tab)
  sẽ phải tự làm thêm (`storage` event chưa xử lý — 2 tab có thể ghi đè nhau).
- **Tech debt**: chưa hỗ trợ sync nhiều tab; chưa có migration schema `localStorage` (`v2` đã đổi key 1
  lần).

## Nếu làm lại thì khác gì

1. Nghe `window.addEventListener('storage')` để 2 tab không ghi đè nhau (hiện tab cuối thắng).
2. Đặt **version + migration** cho `localStorage` ngay từ đầu (đã phải đổi `kb.conversation_id` →
   `kb.chat.v2`).
3. Nếu sau này có nhiều loại state (settings, filters…), chuyển sang Zustand — nhưng chỉ khi đó, không
   trước.

## Revisit

Xem lại khi:

- Cần **sync nhiều tab/thiết bị** thời gian thực, hoặc undo/redo.
- Số loại state client tăng **≥ 3** (lúc đó plumbing tự viết bắt đầu lỗ).
- Bundle cần giảm hoặc team mở rộng (nhiều dev quen Redux/Zustand hơn).
