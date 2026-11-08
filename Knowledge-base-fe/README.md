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
- `conversation_id` của BE được lưu trong `localStorage` (`kb.conversation_id`) ⇒ reload vẫn hỏi tiếp mạch;
  **New chat** sẽ xoá id này.

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
