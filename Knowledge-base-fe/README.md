step 1: npm install --force or --legacy-peer-deps
step 2: npm run dev

## Cấu hình FE (KB-4.1)

Copy `.env.example` → `.env.local` và set backend URL:

```env
# Browser gọi trực tiếp backend (BE: repo Knowledge-base, mặc định port 8000)
NEXT_PUBLIC_API_PROXY_URL=http://localhost:8000
```

`NEXT_PUBLIC_*` được **nhúng vào bundle lúc build** ⇒ đổi URL phải `npm run build` lại (Docker: `--build-arg`,
xem KB-4.7).

## Markdown & citation chip (KB-4.2)

- Câu trả lời của assistant render bằng `components/markdown-message.tsx`: `react-markdown` + `remark-gfm`
  (table/strikethrough/task list) + `rehype-highlight` (syntax highlighting) — **không** dùng
  `dangerouslySetInnerHTML` ⇒ HTML thô trong nội dung hiện ra dạng text (XSS an toàn).
- Code block có label ngôn ngữ + nút **Copy**; table scroll ngang; token màu định nghĩa trong `app/globals.css`
  (`.md-code .hljs-*`, có cả light/dark) — không phụ thuộc CSS theme ngoài.
- Nhãn `[S1]` → chip bấm được (`onCitationClick`), **trừ** khi nằm trong code fence/inline code.
  Việc nối chip → panel nguồn (scroll + highlight) ở **KB-4.3**.

## Docker (KB-4.7)

```bash
# Build image với URL BE nhúng vào bundle (NEXT_PUBLIC_* chỉ đọc được LÚC BUILD)
docker build --build-arg NEXT_PUBLIC_API_PROXY_URL=http://localhost:8000 -t kb-fe:local .
docker run -p 3000:3000 kb-fe:local      # mở http://localhost:3000

# Hoặc chạy cả BE + FE từ repo BE (host port: FE 3010, BE 8010 — dời để không trùng project khác) (port host: FE 3010, BE 8010 — dời để không trùng project khác)
cd ../Knowledge-base && docker compose up -d --build && docker compose ps
# → UI: http://localhost:3010 · API docs: http://localhost:8010/docs
# → UI: http://localhost:3010 · API: http://localhost:8010/docs
```

- Image có `HEALTHCHECK` (dùng `node -e fetch(...)`, `node:20-slim` không có `curl`) ⇒ container lên `healthy`.
- `.dockerignore` chặn `node_modules`/`.next`/`.env*` khỏi build context.
- Đổi `NEXT_PUBLIC_API_PROXY_URL` ⇒ **build lại image**; `docker run -e ...` không có tác dụng.
- `NEXT_PUBLIC_STREAMING=false` cũng truyền được qua `--build-arg` để tắt SSE trong bundle.

## Test / Lint / Typecheck (KB-4.6)

```bash
npm run test        # vitest run — 91 test, ~1.5s, KHÔNG cần BE/network (fetch được mock)
npm run test:watch  # vitest ở chế độ watch
npm run test:e2e    # Playwright — UI thật trên `npm run dev` (:3000), tự bật dev server nếu chưa chạy
npm run test:e2e:prod   # Playwright trên container/production build (:3010)
npm run test:all    # vitest + Playwright
npm run lint        # eslint . (flat config eslint-config-next, 0 error)
npm run typecheck   # tsc --noEmit
npm run build       # next build — CÓ type check thật (ignoreBuildErrors: false)
```

- Test nằm trong `tests/` (jsdom + `@testing-library/react`), setup chung `tests/setup.ts`
  (stub `scrollIntoView`/`clipboard`/`matchMedia`/`ResizeObserver`/`localStorage` vì jsdom thiếu).
- Phạm vi unit: `lib/api.ts` (error envelope + `/ready` 503 + streaming), `lib/sse.ts` (parser + abort),
  `lib/errors.ts` (code → message), `lib/theme.ts` (light/dark/system), `lib/chat-store.ts` (persist),
  `markdown-message`, `sources-panel`, `documents-panel` (gating `CLEAR`/Refresh), `theme-toggle`, `shell`.
- **Chưa có CI/CD** ⇒ các lệnh trên là bộ verify tay trước khi merge MR.

## Verify UI bằng Chromium thật — Playwright (KB-4.9)

Unit test không thấy layout/thẩm mỹ ⇒ có thêm `e2e/ui.spec.ts` chạy **Chromium thật trong WSL**
(0 dependency ngoài `@playwright/test`, **không cần sudo**, không cần Docker).

```bash
bash tools/setup-playwright.sh          # 1 lần: tải lib X11 còn thiếu (không root) + Chromium
npm run test:e2e                        # ~5s cho 7 check, tự bật `npm run dev`
```

| Check | Nội dung |
|---|---|
| Shell | header brand, **đúng 1 nút "Kho tài liệu"**, có theme toggle |
| Responsive | 720px: sidebar ẩn + hamburger + không tràn ngang |
| Theme | sáng → tối: `.dark` + `color-scheme` + `localStorage['kb.theme']` |
| Lịch sử | seed `localStorage` rồi reload: message + tiêu đề session còn, markdown render |
| Lịch sử server (KB-5.2) | `localStorage` rỗng vẫn thấy hội thoại từ `GET /conversations` + messages nạp lazy; BE tắt ⇒ fallback `localStorage`, không trắng màn hình |
| Stream render (KB-5.6) | đang stream: plain text (`**Đậm**` còn nguyên dấu) + **không** có chip; sau `end`: markdown (`<strong>`) + chip `[S1]` bấm được |
| Sheet | `role=dialog`, focus nằm trong sheet, ESC đóng |
| Panel Nguồn | path/snippet dài (kể cả token không dấu cách) **không được rộng hơn cột chat** |
| 1900px | cửa sổ rộng vẫn không tràn ngang |

Ảnh chụp: `test-results/shot-*.png` (light/dark/sheet/nguồn/720/1900) ⇒ dùng để tự review thẩm mỹ.
**Quy ước vòng lặp**: sửa UI → `npm run test:e2e` (dev, ~1–3s/vòng). Docker build **chỉ** khi cần production
parity hoặc cuối ticket (`npm run test:e2e:prod`).

## Kho tài liệu & readiness (KB-4.5)

- `components/documents-panel.tsx`: drawer mở từ header (**Kho tài liệu**) — chỉ fetch khi mở (không poll).
  Tách `DocumentsPanelContent` (thuần props, SSR test được) khỏi `DocumentsPanel` (fetch/state).
- Dữ liệu: `/documents/status` (`document_count`, `collection_name`, `status`) + `/documents/folder-info`
  (`total_files`, `supported_files_count`, `folder_path`) + `/ready` (badge `ok`/`degraded`/`error` + **tên các
  check fail**). `/ready` trả **503** mà vẫn có payload ⇒ `getReady()` đọc body trước, không ném lỗi.
- **Refresh index**: confirm → `POST /documents/refresh` (timeout riêng **30 phút**, `REQUEST_TIMEOUT_CODE` nếu quá)
  → hiện `processed_files`/`total_chunks` rồi tải lại trạng thái.
- **Clear**: phải **gõ `CLEAR`** mới bấm được (Q&A KB-4.5 Q2) → `DELETE /documents/clear`.
- Lỗi hiện theo banner KB-4.1 (`describeApiError`: `code` + message + hint + `request_id`).
- Header **không còn** gọi thẳng `fetch` tới `/documents/refresh|clear` như trước.

## Streaming SSE + nút Stop (KB-4.4)

- `lib/sse.ts`: parser SSE **thuần** (không `fetch`/DOM ⇒ test được bằng `node`) — tách frame theo `\n\n`,
  bỏ comment heartbeat `: ping`, buffer frame bị cắt giữa 2 chunk, chuẩn hoá CRLF; `parseChatEvent()` map
  `start | token | end | error` (JSON hỏng/type lạ → bỏ, không làm chết stream).
- `lib/api.ts`: `streamChat()` — `fetch` + `ReadableStream` reader + `TextDecoder({stream: true})` (tiếng Việt
  không lỗi khi ký tự UTF-8 bị cắt), `AbortController` cho nút **Stop** ⇒ ném `StreamAbortedError`
  (phân biệt với lỗi mạng thật). Lỗi HTTP trước khi stream vẫn là `ApiError` như `apiFetch`.
- `app/page.tsx`: **stream mặc định** — bubble assistant rỗng `isStreaming` rồi nối từng `token`, chốt khi `end`
  (`end.answer` + `sources` + `metadata`), event `error` ⇒ banner KB-4.1 + **giữ partial**; bấm **Stop** ⇒ huỷ
  request, giữ phần đã nhận + nhãn "đã dừng" (Q&A KB-4.4 Q1).
- `NEXT_PUBLIC_STREAMING=false` khi build ⇒ quay lại `POST /chat` blocking (hành vi KB-4.1).

## Panel nguồn theo `citation_id` (KB-4.3)

- `components/sources-panel.tsx`: **1 card / chunk** (không dedup theo `file_path` — trả TD-12), key React là
  `citation_id` (`S1..Sk` do BE sinh theo từng response). Card hiện `[S1]` + `file_name` + `file_type` +
  `chunk #<8 ký tự>` + `heading_path` (fallback `file_path`) + `snippet` (~400 ký tự rồi **Xem thêm**) + `score`.
- Bấm chip `[S#]` trong câu trả lời ⇒ panel scroll card đó vào view + highlight ~2s
  (`highlightCitationId` + `highlightNonce` truyền từ `page.tsx`).
- Footer panel: `model` + `retrieved_documents`. `PiiBadge` giữ ở header message (KB-1.3) để không lặp icon.

## API client & hiển thị lỗi (KB-4.1)

- Mọi call backend đi qua `lib/api.ts` (`apiFetch`, `postChat`) — **không** gọi `fetch` inline trong page.
- Lỗi HTTP được parse theo contract của BE: `{"error": {"code", "message", "request_id"}}` + header `X-Request-ID`
  ⇒ ném `ApiError` (có `code`, `requestId`, `status`).
- `lib/errors.ts` map `code` → **message tiếng Việt** + `hint` + `retryable`; UI hiện banner đỏ kèm `code`,
  `request_id` và nút **Thử lại** (chỉ với lỗi tạm thời: `429/502/503/504`, `network_error`, `service_unavailable`).
- `conversation_id` của BE được lưu trong `localStorage` (`kb.chat_sessions`, KB-4.9) và **cũng** lưu ở server
  (KB-5.2): khi mở app, FE gọi `GET /conversations` để lấy lịch sử (**server là nguồn sự thật**); nếu BE tắt/mất
  mạng thì dùng `localStorage`. Xoá session ⇒ `DELETE /conversations/{id}`. Nội dung lưu ở server là bản **đã
  redact PII** nên hội thoại tải lại có thể hiện `[REDACTED:…]`.

> Phần còn lại của README (proxy Python `server.fastapi_openai_proxy`, `/chat` của repo khác) là **tài liệu cũ**
> từ thời onboarding — backend thật là `Knowledge-base/` (FastAPI, xem README repo đó). Dọn lại ở **TD-20**.

## Quick start (developer)

Prerequisites (dev chuẩn: **WSL2 Ubuntu** — `AGENTS.md` §6, KB-7.1):

- Node.js **LTS** (v26) — cài trong WSL bằng `fnm`: `fnm install --lts` (đừng dùng Node của Windows `/mnt/c`)
- npm (đi kèm Node)

1. Clone the repository and install frontend dependencies

```bash
cd ~/projects/kb-khoa-hoc/Knowledge-base-fe
npm ci            # reproducible theo package-lock.json
```

1b. Production build (verify trước khi commit)

```bash
npm run build
```

2. Set up the Python environment for the backend

```bash
python -m venv .venv
source .venv/bin/activate
# Install minimal backend deps (if you don't have a requirements file)
pip install fastapi uvicorn python-dotenv httpx
```

3. Create a `.env` file at the repository root with at least the following keys:

```env
# OpenAI / upstream chat endpoint (must contain the full completions URL for OpenAI)
OPENAI_API_KEY=sk-...replace...
OPENAI_CHAT_URL=https://api.openai.com/v1/chat/completions

# Which origins are allowed to call the proxy (frontend default is http://localhost:3000)
ALLOWED_ORIGINS=http://localhost:3000

# Frontend will default to http://localhost:8000 if this is unset
NEXT_PUBLIC_API_PROXY_URL=http://localhost:8000
```

Important: Do NOT commit `.env` or secrets to source control.

4. Start the backend proxy

```bash
source .venv/bin/activate
.venv/bin/python -m uvicorn server.fastapi_openai_proxy:app --host 127.0.0.1 --port 8000 --reload
```

5. Start the frontend

```bash
pnpm dev
# or
npm run dev
```

Open the chat UI at: http://localhost:3000/chat

---

## API: Chat endpoint (proxy)

This repository exposes a small proxy endpoint that the frontend calls. Example endpoint (default):

- POST http://localhost:8000/chat

Request JSON (example):

```json
{
  "message": "Kho dữ liệu về chủ đề gì?",
  "conversation_id": "string",
  "max_tokens": 1000,
  "temperature": 0.7
}
```

Successful response (example):

```json
{
	"response": "Kho dữ liệu này về chủ đề \"Sổ tay nhân viên\" của **[COMPANY_NAME]**. ...",
	"conversation_id": "string",
	"sources": [
		{
			"file_path": "documents/EMPLOYEE_HANDBOOK.md",
			"file_name": "EMPLOYEE_HANDBOOK.md",
			"file_type": ".md",
			"relevance_score": 0.184,
			"content_preview": "---\n\n## 21. FAQ (Câu hỏi thường gặp)\n1. **Tôi quên mật khẩu..."
		}
	],
	"metadata": {
		"retrieved_documents": 5,
		"timestamp": "2025-11-06T16:50:12.487196",
		"model": "GPT-4o-mini",
		"temperature": 0.7,
		"max_tokens": 1000
	}
}
