# Phase 4 — Frontend/UX (Done 2026-11-08)

> Mục tiêu phase: FE từ "demo đọc JSON blocking" thành client thật của BE Phase 3 — **contract lỗi**, **markdown thật**,
> **citation bấm được**, **streaming + Stop**, **thấy được trạng thái index/provider**, và **có quality gate**
> (test/lint/typecheck) để không lặp lại chuyện "build xanh mà type sai".
> Nguyên tắc: *FE không tự chế message — mọi thứ hiển thị phải lấy từ contract của BE*.

## Đã có gì sau phase

| Ticket | Kết quả |
|---|---|
| KB-4.1 | **API client duy nhất** `lib/api.ts` (`apiFetch`/`postChat` + `ApiError{code, request_id, status}`) + `lib/errors.ts` map `code` → message tiếng Việt + `retryable`; banner lỗi `role="alert"`; `conversation_id` lưu `localStorage`; `.env.example` |
| KB-4.2 | **Markdown GFM thật** `components/markdown-message.tsx` (`react-markdown` + `remark-gfm` + `rehype-highlight`): code block có label + Copy, table scroll, chip `[S#]` bấm được; **bỏ** `dangerouslySetInnerHTML` ⇒ HTML thô hiện dạng text (XSS-safe) |
| KB-4.3 | **Sources panel theo `citation_id`** `components/sources-panel.tsx`: 1 card / chunk (**trả TD-12**), `chunk #8` + `heading_path` + snippet expand + score; bấm chip ⇒ scroll + highlight 2s |
| KB-4.4 | **Streaming SSE + Stop** `lib/sse.ts` (parser thuần: `\n\n`, bỏ `: ping`, buffer frame bị cắt, `TextDecoder(stream)`) + `streamChat()` (`AbortController` ⇒ `StreamAbortedError`); UI nối token, `end` chốt `answer`/`sources`, Stop **giữ** partial + nhãn "đã dừng"; `NEXT_PUBLIC_STREAMING=false` ⇒ fallback `/chat` |
| KB-4.5 | **Kho tài liệu + readiness** `components/documents-panel.tsx` (drawer từ header): `/documents/status` + `/documents/folder-info` + `/ready` (503 vẫn đọc payload) + Refresh (confirm, timeout 30') + Clear (phải gõ `CLEAR`); header **bỏ `fetch` inline** hardcode `localhost:8000` |
| KB-4.6 | **Quality gate**: `vitest` + `jsdom` + `@testing-library` (**50 test / 6 file, ~1.2s**), `eslint.config.mjs` (flat, `eslint-config-next`), script `typecheck`, **`ignoreBuildErrors: false`** (build type-check thật); xoá `feedback-modal` + `lib/rbac` (code chết) |
| KB-4.7 | **Docker FE + compose BE↔FE**: `ARG NEXT_PUBLIC_*` nhúng lúc build, `HEALTHCHECK` (`node -e fetch`), `.dockerignore`; compose bỏ mount source, `depends_on: service_healthy`, `user: ${USER_ID}` + `HF_HOME` volume, `start_period 600s` |

## Cách chạy ở thời điểm này

```bash
# --- FE dev (ngoài Docker) ---
cd Knowledge-base-fe
npm ci
cp .env.example .env.local          # NEXT_PUBLIC_API_PROXY_URL=http://localhost:8000
npm run dev                         # http://localhost:3000

# --- Quality gate FE (bắt buộc trước khi merge MR) ---
npm run test        # 50 test, ~1.2s, không cần BE
npm run lint        # 0 error (vài warning `any` ở export-utils)
npm run typecheck   # tsc --noEmit
npm run build       # có "Running TypeScript" — fail nếu type sai

# --- Cả hệ thống bằng Docker ---
cd Knowledge-base
docker compose up -d --build        # chatbot-api :8000 + chatbot-ui :3000
docker compose ps                   # cả 2 phải healthy

# --- Kiểm tra tay ---
curl -s localhost:8000/health
curl -s localhost:8000/ready        # ok | degraded | error(503)
curl -sN -X POST localhost:8000/chat/stream -H 'Content-Type: application/json' \
  -d '{"message":"List 3 Java collection types.","max_tokens":200}'
```

## Contract chốt trong phase

| Contract | Nội dung |
|---|---|
| Lỗi | Mọi lỗi hiển thị theo `error.code` + `request_id`; FE **không** hiện `error.message` tiếng Anh của BE; `retryable` quyết định nút "Thử lại" |
| Streaming | Mặc định bật (`NEXT_PUBLIC_STREAMING`); event `start → token* → (end \| error)`; `end.answer` là nguồn sự thật; Stop **không** phải lỗi |
| Citation | `[S#]` ↔ `citation_id` 1-1, **1 chunk = 1 card**; chip không sinh trong code fence |
| Nguồn/metadata | `sources[]` giữ nguyên thứ tự BE, **không dedup** theo `file_path` |
| Env | `NEXT_PUBLIC_*` là **build-time** ⇒ đổi URL phải build lại (Docker: `--build-arg`) |
| XSS | Không `dangerouslySetInnerHTML`; HTML thô trong câu trả lời = text |

## Cái gì CHƯA có (đừng tưởng đã có)

- **Chưa có CI/CD**: `test/lint/typecheck` vẫn là bước **chạy tay**; không có gì chặn merge tự động.
- **Chưa test E2E/Playwright**: click thật trên browser (chip citation, Stop, Refresh/Clear) **chưa** được test tự động —
  đó là lý do các ticket 4.2–4.5 ghi rõ "verify bằng SSR smoke / `curl`".
- **Streaming chưa tối ưu**: mỗi token render lại toàn bộ markdown (**TD-21**).
- **`MessageWithCitations` còn nhánh render `sources`/`citations` chết** (~130 dòng) — **TD-22**.
- **`/ready?deep=true` chưa có UI** (tốn quota provider) — **TD-23**; refresh index **không có tiến trình**.
- **Auth/RBAC chưa có**: `role-badge` chỉ là UI tĩnh; đăng nhập thật để Phase 5.
- **i18n**: message tiếng Việt hardcode; chưa có cơ chế đa ngôn ngữ.
- **Docker**: model ~3.3GB không bake vào image (**TD-24**), FE image 1.07GB, chưa có registry/CI build.

## Bài học

- **Muốn test được thì phải tách pure khỏi I/O**: `lib/sse.ts`, `lib/errors.ts`, `DocumentsPanelContent` không cần browser
  ⇒ 50 test chạy 1.2s. Những chỗ gắn chặt vào `fetch`/`useEffect` thì chỉ verify được bằng smoke `node` + `react-dom/server`.
- **Verify UI không cần browser**: `tsc` component → `react-dom/server` → assert markup là cách rẻ nhất bắt bug thật
  (đã bắt được `citation://` bị react-markdown strip `href`).
- **Rule mới của React Compiler (`purity`, `set-state-in-effect`) buộc phải nói rõ chủ ý**: chỗ nào cố ý thì hạ `warn`
  + ghi lý do trong config, không tắt ngầm.
- **Docker: quyền file quan trọng hơn config**: bind mount + container non-root ⇒ "readonly database"; override `user`
  lại kéo theo `HOME`/cache. Mọi thứ "chạy được trên máy dev" đều có thể chết trong container vì uid.
