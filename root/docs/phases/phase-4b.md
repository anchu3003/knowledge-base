# Phase 4b — UI/UX overhaul (Done 2026-11-08)

> Mục tiêu phase: UI từ "bản onboarding dựng vội" thành **sản phẩm dùng được hằng ngày** — design system thật,
> dark mode, layout chuẩn, **không còn control giả**, lịch sử hội thoại không mất khi F5, **không mất dữ liệu index**,
> và **nói rõ đang làm gì** khi chờ 13s.
> Nguyên tắc: *UI chỉ hiển thị/cho thao tác những gì backend thật sự hỗ trợ; cái gì chưa có thì không giả vờ.*

Sinh ra từ **audit 2026-11-08** khi chạy UI thật trong Docker (4 lỗi: control giả, layout hẹp, dark mode chết, và
một **lỗi mất dữ liệu tiềm tàng** ở `POST /documents/refresh`).

## Đã có gì sau phase

| Ticket | Kết quả |
|---|---|
| KB-4.8 | **Design system + shell**: 9 primitive shadcn dựng từ Radix **đã cài** (`sheet`/`tooltip`/`toast`/`badge`/`separator`/`skeleton`/`slider`/`label`/`avatar`) — **0 dependency mới**; layout 2 cột (`max-w-3xl` + composer sticky), sidebar → `Sheet` ở mobile; **theme light/dark/system** (`lib/theme.ts` + `useSyncExternalStore` + script inline chống FOUC); typography `.md-body`; `page.tsx` **788 → tách 5 component**; bỏ `chat-history-sidebar`, `role-badge` (dead code) |
| KB-4.9 | **Bỏ control giả + multi-conversation phía client**: `lib/chat-store.ts` (store ngoài React + `localStorage['kb.chat_sessions']`, tối đa 50 session, ghi **debounce 300ms**, migrate key cũ); `conversation_id` **theo từng session**; title tự sinh từ câu hỏi đầu; bỏ nút **Kho tài liệu** ở sidebar; **Sao chép** ra ngoài bubble + toast; `max_tokens` 500 → **1000** |
| KB-4.10 | **An toàn dữ liệu index (BE+FE)**: compose mount `./Interview:/app/Interview:ro`; refresh trả **409 `documents_folder_empty`** *trước* `clear_database()`; lifespan chỉ auto-load khi collection **rỗng** (hết 9+ phút mỗi lần start) + log đúng tên folder; FE **chặn nút Refresh** + hiện lý do |
| KB-4.11 | **Streaming UX**: `lib/stream-phase.ts` (`phaseOf`) + `components/stream-status.tsx` — nhãn **"Đang truy hồi tài liệu… (7s)"** (trước `start`) → **"Đang viết câu trả lời…"** (sau `start`) + skeleton + gợi ý rerank CPU; `end.answer` rỗng ⇒ **cảnh báo amber + nút Thử lại** thay vì bubble trống |

## Cách chạy ở thời điểm này

```bash
# --- Vòng lặp dev UI (nhanh, ~1-3s/vòng) ---
cd Knowledge-base-fe
cp .env.example .env.local                 # NEXT_PUBLIC_API_PROXY_URL=http://localhost:8010
npm run dev                                # http://localhost:3000
npm run test:e2e                           # Playwright (tự bật dev server) — 10 check, ~10s

# --- Quality gate FE (bắt buộc trước khi merge MR) ---
npm run test        # vitest: 12 file / 103 test (~1.5s), không cần BE
npm run lint        # 0 error (6 warning cũ)
npm run typecheck   # tsc --noEmit
npm run build       # next build + type check thật

# --- Docker (production parity — chỉ khi cần) ---
cd Knowledge-base
docker compose up -d --build                        # chatbot-api :8010 + chatbot-ui :3010
npm --prefix ../Knowledge-base-fe run test:e2e:prod  # Playwright trên bản build thật

# --- Cài Playwright lần đầu (không cần sudo) ---
cd Knowledge-base-fe && bash tools/setup-playwright.sh
```

Đo được: dev loop ~1–3 s/vòng · e2e **~10s** (dev) / **~9s** (prod) · Docker rebuild **~90s**.

## Cái gì CHƯA có (đã ghi tech debt)

| Nợ | Nội dung | Điều kiện revisit |
|---|---|---|
| TD-15 | Rerank CPU **~8–13 s/query** ⇒ `start` đến sau 12,9 s. Phase này chỉ **giải thích** cho người dùng, chưa làm nhanh | Khi cần latency thấp (vé vào Phase 5) |
| TD-21 | Mỗi token render lại toàn bộ markdown ⇒ tốn CPU client với câu trả lời dài | Khi UI giật với câu trả lời > ~1000 token |
| TD-22 | `MessageWithCitations` còn nhánh render `sources`/`citations` **chết** (~130 dòng) | Khi dọn dead code FE (ticket riêng) |
| TD-23 | `/ready?deep=true` chưa có UI; refresh index **không có tiến trình** | Khi refresh chạy dài mà cần %/trạng thái |
| TD-24 | **Chưa có CI/CD** + chưa có registry; Playwright đã sẵn sàng để wire | Khi thêm pipeline (GitLab CI) |
| TD-25 | Auto-load lần đầu vẫn index **đồng bộ trong lifespan** ⇒ container mới với folder lớn lâu healthy | Khi deploy thật (rolling update) |
| TD-2 | Conversation **phía BE** vẫn in-memory ⇒ restart mất mạch server-side (FE đã lưu client) | Khi cần lịch sử bền vững/nhiều thiết bị |

Chưa làm (ngoài scope phase, đã có vé ở Phase 5): **upload tài liệu từ UI** (BE chưa có endpoint, `Interview` mount **ro**),
**auth**, **cache câu trả lời**.

## Bài học

1. **`.dockerignore` + bind mount = lỗi mất dữ liệu âm thầm.** Image thiếu folder tài liệu nhưng volume vẫn đủ chunk ⇒
   panel hiện "0 file" trong khi index 601 chunk, và `refresh` (clear → load) sẽ **xoá sạch**. Bài học: **endpoint phá huỷ
   phải tự kiểm tra điều kiện tiên quyết**, và test phải assert `clear_database` **không** được gọi.
2. **Unit test không thấy layout.** Ba lỗi thẩm mỹ (bubble full-width, nút Sao chép đè chữ, panel Nguồn thò ra ngoài cột)
   chỉ lộ khi **chụp ảnh Chrome thật**.
3. **`document.scrollWidth` không bắt được tràn ngang** khi container có `overflow:hidden` (Radix ScrollArea) ⇒ phải so
   **kích thước với cột chuẩn** (composer). `getByText(string)` của Playwright là case-insensitive + substring ⇒ cần
   `{exact: true}` + scope.
4. **`route.fulfill()` không test được streaming** vì trả cả body một lần ⇒ phải dựng **SSE server thật** (`node:http`)
   mới quan sát được chuyển pha `retrieving → writing`.
5. **State client persist + SSR**: `useSyncExternalStore` với `getServerSnapshot` **rỗng** — không lệch hydration, không
   vướng `react-hooks/set-state-in-effect`.
6. **Đừng "giữ control giả cho đủ scope"**: viết lại shell thì select `Model` / textarea `System prompt` tự rơi ra vì
   chúng chưa bao giờ được gửi lên BE. Cái **bị bỏ** quan trọng hơn cái được thêm.
7. **Spinner câm là lỗi UX**: người dùng chịu được chờ, không chịu được mù thông tin.
8. **Tự gây sự cố rồi sửa**: script python mở `Backlog.md` bằng `open('w')` rồi crash ⇒ mất sạch file (khôi phục từ
   VS Code local history + `docs/phases/*`). Từ đó: **ghi atomic (`tmp` + `os.replace`)** cho mọi file nguồn sự thật.
