# architecture.md — Kiến trúc Knowledge Base (cá nhân)

> Nguồn sự thật về kiến trúc, tech stack và roadmap. Cập nhật file này khi design đổi
> (`AGENTS.md` §3.3). Quyết định lớn ghi thêm ADR trong `docs/adr/` — hiện có `0001-llm-provider-groq.md`;
> **Phase 8 (KB-8.1…8.5)** đang backfill ADR cho 16 quyết định cũ + tạo `docs/adr/README.md` làm lộ trình học.

---

## 1. Tổng quan

**Knowledge Base** là một **RAG chatbot cá nhân**: hỏi đáp trên tài liệu cá nhân (ghi chú kỹ thuật,
ôn phỏng vấn, học tiếng Anh, tài liệu tự học). Người dùng hỏi → hệ thống **retrieval** các chunk
liên quan từ vector store → đưa context cho **LLM** → trả lời có trích dẫn nguồn.

Đặc điểm:

- **Single user** (chính tôi). Không multi-tenant.
- **Privacy-first**: tài liệu cá nhân → **che PII/secret trước khi gửi LLM** (§7).
- **Chi phí**: embeddings chạy **local** (miễn phí); LLM dùng **free tier** (Groq).

---

## 2. Sơ đồ hệ thống

```
┌────────────────────────┐        ┌────────────────────────────────────────┐
│  Knowledge-base-fe     │  HTTP  │           Knowledge-base (BE)           │
│  Next.js 16 (UI)       │ ─────► │           FastAPI · :8000               │
│  :3000                 │ /chat  │                                         │
│                        │◄────── │  ┌──────────────┐   ┌────────────────┐  │
│  - chat UI             │  JSON  │  │ ChatService  │──►│ PIIRedactor    │  │
│  - markdown render     │        │  └──────┬───────┘   └────────────────┘  │
│  - sources panel       │        │         │ (context)                     │
└────────────────────────┘        │         ▼                               │
                                  │  ┌───────────────────┐                  │
                                  │  │ DocumentService    │                  │
                                  │  │ (ChromaDB + BM25)  │                  │
                                  │  └───────────────────┘                  │
                                  └───────────┬─────────────────────────────┘
                                              │ HTTPS (OpenAI-compatible)
                                              ▼
                                  ┌───────────────────────┐
                                  │  LLM provider (Groq)  │  ← free tier
                                  └───────────────────────┘

Embeddings: Qwen/Qwen3-Embedding-0.6B (đa ngữ, 1024-d)  → chạy LOCAL (CPU)
Vector store: ChromaDB (local, ./chroma_db)
```

---

## 3. Hai repo

| | Backend | Frontend |
|---|---|---|
| Thư mục | `Knowledge-base/` | `Knowledge-base-fe/` |
| Stack | Python 3.13 · FastAPI · LangChain · ChromaDB | Next.js 16 · React 19 · TS · Tailwind v4 · shadcn |
| Port dev | `8000` | `3000` |
| Remote | `gitlab.com:anchu3003/knowledge-base-be` | `gitlab.com:anchu3003/knowlege-base-fe` |
| Điểm vào | `app/main.py` | `app/page.tsx`, `app/chat/page.tsx`, `app/login/page.tsx` |

### 3.1 Môi trường dev — WSL2 (KB-7.1)

| Hạng mục | Giá trị |
|---|---|
| OS dev | **WSL2 Ubuntu 26.04** (kernel `6.18.x-microsoft-standard-WSL2`), `/etc/wsl.conf` bật `systemd=true` |
| Vị trí code | `/home/anchu/projects/kb-khoa-hoc` — **Linux FS**, không dùng `/mnt/*` (I/O chậm với `node_modules`/torch) |
| Python | **3.13.18** qua `uv` (venv `Knowledge-base/.venv`) |
| Node | **26.13.0** LTS qua `fnm` (npm 11.20) |
| Docker | `docker build` chạy được (engine 29.9.2); image BE **2,68 GB** (KB-5.10: torch CPU + bind-mount `/wheels`), FE 1,1 GB — chưa có registry/CI: **TD-24** |
| GitLab CLI | `glab 1.128.0` (auth bằng PAT scope `api`) |
| Editor | VS Code + **Remote-WSL** |

Windows chỉ còn VS Code/Remote-WSL. Chi tiết lệnh: `AGENTS.md` §6.

---

## 4. Backend — chi tiết

### Layer

- `app/main.py` — FastAPI routes + lifespan (khởi tạo service, auto-load docs).
- `app/services/chat_service.py` — `ChatService`: gọi LLM, RAG loop, streaming, query-rewrite.
- `app/services/document_service.py` — `DocumentService`: load/chunk/embed docs vào ChromaDB, retrieval (dense + BM25 + rerank).
- `app/services/conversation_store.py` — `ConversationStore` (KB-5.2): lịch sử hội thoại bền, 1 file SQLite
  (`CHAT_DB_PATH`, mặc định `./data/chat.db`, WAL) với 2 bảng `conversations`/`messages`; `save()` = 1
  transaction (upsert + replace), `load/list/delete`, `prune` giữ `MAX_CONVERSATIONS=200` session.
- `app/services/pii_service.py` — `PIIRedactor`: che PII/secret (thêm ở Phase 1).
- `app/models/schemas.py` — pydantic request/response.
- `app/core/errors.py` — **error taxonomy** (KB-3.1): `AppError` + subclass (`ProviderAuthError` 502,
  `ProviderRateLimitError` 429, `ProviderUnavailableError` 503, `ProviderTimeoutError` 504,
  `DocumentStoreError` 500, `NotFoundError` 404, `ServiceUnavailableError` 503) + `map_provider_error()`.
- `app/core/middleware.py` — `RequestIDMiddleware` (pure ASGI): gán `request_id` (header client nếu hợp lệ,
  không thì uuid4) vào `request.state` + trả header `X-Request-ID` + log 1 dòng/request.
- `app/core/provider_retry.py` — **cổng duy nhất gọi provider** (KB-3.2): `ProviderThrottle` =
  `asyncio.Semaphore(PROVIDER_MAX_CONCURRENCY)` + retry có ngân sách (chỉ `429`/`5xx`/timeout/connection),
  exponential backoff + jitter, tôn trọng `Retry-After`; hết ngân sách → `ProviderRateLimitError` /
  `ProviderTimeoutError` / `ProviderUnavailableError`.
- `app/core/sse.py` — transport SSE (KB-3.3): `SSE_HEADERS` (chống buffer/tắt cache), `error_event()`,
  `sse_event_stream()` (task bơm event + queue ⇒ heartbeat `: ping` không đụng generator; disconnect thì
  cancel task và **await** để generator dọn dẹp).
- `app/services/health_service.py` — probe (KB-3.4): `liveness()` (`/health`, luôn 200) và `readiness()`
  (`/ready`: `provider_config` + `prompt_file` + `collection`, `deep=true` mới gọi provider 1 request `max_tokens=1`).
- `app/core/config.py` — `Settings` (đọc env). **Lưu ý:** bỏ hard-code `OPENAI_BASE_URL` (KB-0.2).
- `eval/` — **eval harness** (`run_eval.py` + `qa_set.json` + `runs/`): đo `hit@k`, `MRR`, `dup_ratio`,
  `distinct_file_ratio`, `citation_presence` (KB-2.1). Không phải runtime code — chỉ dùng để verify/tune.

### Luồng chat (`POST /chat`)

```
message
  → [PII redact]                     # che trước khi ra ngoài
  → initial retrieval (dense+BM25)   # ChromaDB
  → (nếu score kém) query rewrite    # gọi LLM → rewrite (cũng phải redact)
  → dedup + cap/file (KB-2.2)
  → rerank (cross-encoder, local)
  → build context có nhãn [S1]..[Sk] (budget CONTEXT_MAX_CHARS)   # KB-2.3
  → system prompt (rule cite [S#] + "không có trong knowledge base")
  → [PII redact context]             # che PII trong tài liệu trước khi gửi LLM
  → ChatOpenAI (Groq) → answer có [S#] + sources[{citation_id, chunk_id, snippet}]
  → lưu hội thoại vào SQLite         # KB-5.2 (user message đã redact)
```

### Lịch sử hội thoại bền (KB-5.2)

```
POST /chat ──► ChatService ──► RAM (self.conversations)  ──► ConversationStore (SQLite)
                             ◄── lazy-load khi cache miss ◄── ./data/chat.db (WAL)

FE mở app ──► GET /conversations ──► merge vào chat-store (server = nguồn sự thật)
             └─ lỗi/timeout ──────► giữ lịch sử trong localStorage (không trắng màn hình)
chọn session ──► GET /conversations/{id} (nạp messages lazy)
xoá session ──► DELETE /conversations/{id}
```

- Endpoint: `GET /conversations` (list + `message_count`), `GET /conversations/{id}` (messages),
  `DELETE /conversations/{id}` (**404** nếu không tồn tại). Không đổi contract `/chat`.
- `content` lưu xuống DB là bản **đã redact PII** ⇒ reload từ server có thể thấy `[REDACTED:…]`.
- `MAX_CONVERSATIONS=200` — vượt thì xoá session cũ nhất; file DB nằm trong volume `./data`
  (đã `.gitignore`, không commit vì chứa nội dung chat).


### RAG features hiện có

> **Vì sao** các lựa chọn dưới đây: ADR [`0002`](docs/adr/0002-vector-store-chromadb.md) (vector store) ·
> [`0003`](docs/adr/0003-embedding-model-qwen3.md) (embedding) · [`0004`](docs/adr/0004-chunking-markdown-heading.md)
> (chunking) · [`0005`](docs/adr/0005-hybrid-search-bm25.md) (hybrid) ·
> [`0006`](docs/adr/0006-rerank-cross-encoder.md) (rerank) ·
> [`0010`](docs/adr/0010-eval-la-cong-chat-luong.md) (eval gate).


- **Chunking** (KB-2.4): `.md` tách **2 tầng** — `MarkdownHeaderTextSplitter` (H1–H3) → mỗi section
  qua `RecursiveCharacterTextSplitter` (`CHUNK_SIZE`/`CHUNK_OVERLAP`). Metadata: `heading_path`
  (`"Java > Core > Collections"`), `chunk_index` (theo file), `chunk_id` (sha1).
- Hybrid retrieval: dense (Chroma) + BM25 (`rank-bm25`), trộn theo `HYBRID_ALPHA`.
- **Hậu xử lý kết quả** (KB-2.2): dedup chunk gần trùng (`DEDUP_ENABLED`, Jaccard shingle 3-gram ≥
  `DEDUP_JACCARD_THRESHOLD=0.8`) + **cap `MAX_CHUNKS_PER_FILE=2`** để top-k phủ nhiều tài liệu
  (dedup chạy cả trước và sau rerank). `chunk_id` trả về trong mỗi hit.
- **`SIMILARITY_THRESHOLD`** = ngưỡng cosine tối thiểu cho **dense candidates** (default `0` = tắt);
  **không** áp cho score hybrid (đã min-max normalize) hay rerank (logits). Đo giá trị ở KB-2.5 —
  đặt 0.7 khi chưa đo làm `hit@k` rơi từ 0.933 xuống 0.333.
- **Chunk ID ổn định** `sha1(source|chunk_index|text)[:16]` + `collection.upsert` ⇒ ingest lặp không
  sinh bản trùng (KB-2.2).
- Re-ranking: cross-encoder `BAAI/bge-reranker-v2-m3` (đa ngữ, local) — cấu hình qua `RERANK_MODEL`.
  **KB-5.3 (trả TD-15)** giảm 20 → 8; **KB-5.8 (trả TD-29)** đo lại trên bộ vàng **20 câu** rồi chốt **6**:
  `latency_p50` **9,70 → 3,44 s** và precision@k **0,617 → 0,617** (không đổi), `distinct_file_ratio` 0,783.
  Mỗi phần của multi-query giờ chấm **đủ** `RERANK_TOP_N` (trước là `top_n//2` — đo lại thấy precision tụt >5%).
- **Cache rerank** (`app/services/rerank_cache.py`, KB-5.3): LRU + TTL trong RAM, khoá =
  `query normalize + index_version + k + top_n + config fingerprint`. `index_version` tăng ở `upsert`/`delete`/
  `clear` ⇒ sync tài liệu là cache tự vô hiệu (không dùng lại kết quả của index cũ). Câu lặp: **7,15 → 0,13 s**.
  Điểm toàn `0.0` (encoder lỗi) **không** được cache. `GET /documents/status` trả thêm `index_version` +
  `rerank_cache` (`hits`/`misses`/`hit_rate`) để quan sát.
- **Multi-query** (KB-5.4, `app/services/multi_query.py`): câu hỏi **nhiều ý** ("A và B khác nhau thế nào?") được
  tách bằng **heuristic** (`và` / `so với` / `;` / `, khi nào|tại sao…`, bảo vệ nội dung trong ngoặc kép/backtick,
  tối đa `MULTI_QUERY_MAX_PARTS=3`), retrieve **từng phần song song** (mỗi phần chỉ chấm `top-N/2` ứng viên) rồi gộp
  theo `chunk_id` (giữ score cao nhất). Mặc định BẬT; tắt bằng `MULTI_QUERY_ENABLED=false` để A/B.
  Đo (bộ vàng v3 = 20 câu, cache tắt): `precision@k` 0,533 → **0,617**, `hit@k`/`MRR` giữ nguyên, `latency_p50`
  9,70 → **6,50 s**. Control `top-N=4` 1 bước cho MRR 1,0 + 2,0 s ⇒ đòn bẩy lớn nhất vẫn là `RERANK_TOP_N` (TD-29).
  Metadata `/chat` + `start` event thêm `multi_query_parts` / `multi_query_enabled` (additive, contract không đổi).
- Query rewrite khi retrieval kém (`ENABLE_QUERY_REWRITE`, threshold `REWRITE_MIN_RESULTS` / `REWRITE_MIN_TOP_SCORE`).
- Streaming: `POST /chat/stream` (SSE).

### Error contract & request-id (KB-3.1)

> **Vì sao**: ADR [`0008`](docs/adr/0008-error-taxonomy-va-retry.md) — bảng ánh xạ lỗi → HTTP → code +
> lý do chỉ có **một** cổng gọi provider.


```
service raise AppError ──► exception handler (app/main.py) ──► {"error": {code, message, request_id}}
                                                              + response header X-Request-ID
```

- `AppError` (`app/core/errors.py`) là **nguồn sự thật duy nhất** về lỗi; `main.py` không còn
  `HTTPException(detail=f"...{str(e)}")` ⇒ client nhận `code` hằng số thay vì string tự do.
- Handler: `AppError` → status của nó; `RequestValidationError` → 422 (+`error.details[]` loc/msg/type,
  không echo input); `StarletteHTTPException` → 404/405… cùng envelope; `Exception` → 500 `internal_error`.
- Chi tiết nội bộ (`str(e)`, host provider, path, traceback) **chỉ** vào log, kèm `request_id`.
- `ChatService` map lỗi SDK provider qua `map_provider_error()` (`AuthenticationError` → 502,
  `RateLimitError` → 429, `APITimeoutError` → 504, `APIConnectionError`/`APIError` → 503); `stream_chat`
  yield event `{"type": "error", "code", "message"}` (SSE đầy đủ ở KB-3.3).

### Gọi provider: retry + timeout + concurrency (KB-3.2)

```
ChatService.chat / stream_chat        (query rewrite: throttle only, KHÔNG retry)
        │
        ▼
ProviderThrottle  ── asyncio.Semaphore(PROVIDER_MAX_CONCURRENCY=1)   # serialize, không vượt TPM 8000
        │
        ├── retryable? 429 / 5xx / timeout / connection  → backoff (Retry-After ưu tiên) + jitter
        │                                                → hết budget: 429 / 504 / 503
        └── không retryable (401/400/…)                  → fail ngay (retry chỉ tốn quota)

SDK: ChatOpenAI(timeout=PROVIDER_TIMEOUT_SECONDS, max_retries=0)   # service quyết định retry DUY NHẤT
```

- Stream: retry **chỉ trước token đầu tiên** (token đã gửi thì không retry được) — semaphore giữ suốt stream.
- Log retry chỉ có `op / attempt / error / delay` — **không** prompt/context (PII rule §7).

### `/chat/stream` — SSE contract (KB-3.3)

> **Vì sao** heartbeat + chống buffer + lưu partial khi client ngắt: ADR
> [`0009`](docs/adr/0009-sse-streaming-contract.md).


```
client ──POST /chat/stream──► endpoint (main.py)
                              │  request_id từ middleware
                              ▼
                    sse_event_stream()  ── task bơm event + asyncio.Queue
                              │              ├─ quá SSE_HEARTBEAT_SECONDS ⇒ ": ping\n\n"
                              │              └─ disconnect ⇒ cancel task + await (dọn dẹp)
                              ▼
                    ChatService.stream_chat()   start → token* → (end | error)
```

- Thứ tự cố định: **`start → token* → (end | error)`**, luôn có đúng một event kết thúc.
- `error` = `{"type": "error", "error": {code, message, request_id}}` (cùng schema envelope `/chat`).
- Header: `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`.
- Disconnect: `CancelledError`/`GeneratorExit` → lưu partial answer (`interrupted: true`) nếu đã có ≥1 token,
  log `info` không stack (Q&A KB-3.3).

### Probes: `/health` (liveness) + `/ready` (readiness) — KB-3.4

```
GET /health ──► HealthService.liveness()            200 luôn (process sống)
                └ version + uptime_seconds (tính từ lifespan start)

GET /ready  ──► HealthService.readiness(deep=False)
                ├ provider_config  (có OPENAI_API_KEY/MODEL/BASE_URL? — chỉ kiểm "có", không kiểm đúng/sai)
                ├ prompt_file      (SYSTEM_PROMPT_PATH tồn tại?)
                └ collection       (Chroma count > 0?)
                ⇒ ok (200) | degraded (200, thiếu docs) | error (503, thiếu config/prompt)

GET /ready?deep=true ──► + provider probe: 1 request `max_tokens=1` (tốn quota ⇒ MẶC ĐỊNH TẮT,
                         không dùng trong Docker HEALTHCHECK)
```

- Probe **rẻ**: đo thật `/health` 8.6ms, `/ready` 1.8ms (không import model, không gọi mạng).
- Body của `/ready` là `{status, checks}` (**không** dùng envelope `{"error": ...}` — đây là probe cho orchestrator);
  `checks.*.detail` không chứa secret/`str(e)`, chỉ tên biến env còn thiếu.
- `Dockerfile` có `HEALTHCHECK ... curl /health` với `--start-period=180s` (lần đầu tải embedding model).

### Env chính (`app/core/config.py`)

| Biến | Ý nghĩa |
|---|---|
| `OPENAI_API_KEY` | key provider (Groq: `gsk_…`) |
| `OPENAI_BASE_URL` | endpoint OpenAI-compatible (Groq: `https://api.groq.com/openai/v1`) |
| `OPENAI_MODEL` | model (Groq: `openai/gpt-oss-120b`) |
| `ENABLE_PII_REDACTION` | bật/tắt redaction (mặc định `true`) |
| `PII_REDACT_INGEST` | có che PII lúc index tài liệu không |
| `ENABLE_BM25` / `ENABLE_HYBRID` / `ENABLE_RERANK` | cờ retrieval |
| `RERANK_TOP_N` | số ứng viên đưa vào cross-encoder (KB-5.8: default **6** — p50 3,44 s, precision@k 0,617; mỗi phần multi-query cũng chấm đủ top-N) |
| `AUTH_ENABLED` / `API_TOKEN` | auth token tĩnh (KB-5.5): **mặc định `false`**; bật ⇒ client gửi `X-API-Key`, `/` + `/health` công khai, `/ready` bảo vệ, token rỗng = fail-closed |
| `LOG_LEVEL` | level logger `app.*` (KB-5.9: default `INFO`; thư viện ồn ào luôn ≥ `WARNING`) |
| `RERANK_CACHE_ENABLED` / `RERANK_CACHE_TTL_SECONDS` / `RERANK_CACHE_MAX_ENTRIES` | cache rerank trong RAM (KB-5.3: bật, TTL 3600 s, 256 entry) |
| `PROVIDER_TIMEOUT_SECONDS` / `PROVIDER_MAX_RETRIES` / `PROVIDER_RETRY_BASE_DELAY` / `PROVIDER_MAX_CONCURRENCY` | retry + timeout + số call đồng thời tới provider (KB-3.2) |
| `SSE_HEARTBEAT_SECONDS` | nhịp heartbeat `: ping` của `/chat/stream` (KB-3.3) |
| `CHAT_DB_PATH` | file SQLite lịch sử hội thoại (KB-5.2, mặc định `./data/chat.db`; để rỗng ⇒ chỉ in-memory) |
| `MAX_CONVERSATIONS` | số session giữ trong DB (KB-5.2, mặc định `200`, vượt ⇒ xoá cũ nhất) |
| `DOCUMENTS_FOLDER` | thư mục tài liệu (mặc định `Interview`) |

---

## 4b. CI (KB-5.7) — có sẵn nhưng **TẮT mặc định**

| Repo | File | Job | Ghi chú |
|---|---|---|---|
| `Knowledge-base` | `.gitlab-ci.yml` | `pytest` | `python:3.13-slim` · cài **torch CPU** trước (như `Dockerfile`, KB-5.10) · cache pip · artifact `junit` |
| `Knowledge-base-fe` | `.gitlab-ci.yml` | `lint-typecheck-test` · `build` · `e2e` | `node:22` · e2e dùng image `mcr.microsoft.com/playwright:v1.65.0-jammy` · `next start` + `APP_URL` (không dùng `next dev`) |

- **Cờ**: `workflow.rules` chỉ cho pipeline chạy khi biến CI/CD **`CI_ENABLED=true`**; chưa đặt ⇒ `when: never`
  ⇒ **không tạo pipeline** (merge condition vẫn như cũ: ticket Done + MR có summary + không conflict).
  Bật: Settings → CI/CD → Variables → thêm `CI_ENABLED=true` (không cần Protected/Masked).
- e2e trong CI **không cần** BE/LLM/quota: toàn bộ test stub route (`/chat/stream`, `/conversations`, `/documents/*`).
- **Chưa có**: build/push **registry**, deploy, bake model (TD-24). Thời gian pipeline thật chưa đo (chưa bật cờ).

---

## 5. Frontend — chi tiết

> **Vì sao** FE không dùng thư viện state và không render markdown khi stream: ADR
> [`0015`](docs/adr/0015-fe-state-khong-dung-thu-vien.md) ·
> [`0016`](docs/adr/0016-render-streaming-plain-text.md).


- App Router (`app/`): chỉ có `layout.tsx` + `page.tsx` (màn chat chính) — **không** còn `chat/`, `login/` như bản onboarding.
- `components/` (KB-4.8 tách `page.tsx` 788 dòng thành component nhỏ):
  `app-providers` (Tooltip + Toast provider), `app-header` (brand + **nút Lịch sử** mở ngăn kéo + Kho tài liệu +
  theme toggle), `app-sidebar` (**chỉ** là nội dung ngăn kéo từ KB-5.11 — không còn cột cố định; nút xoá session
  luôn hiển thị), `chat-messages` (bubble full-width + `Skeleton`), `chat-composer`
  (sticky, Enter gửi / Shift+Enter xuống dòng, `Slider` cho temperature), `error-banner` (KB-4.1),
  `theme-toggle` (`lib/theme.ts`), `toast-provider`/`useToast`, `message-with-citations`, `markdown-message`
  (KB-4.2), `sources-panel` (KB-4.3), `documents-panel` (KB-4.5, nay là `Sheet` nên có focus trap/ESC/`aria-modal`),
  `pii-badge` (KB-1.3), `typing-indicator`.
- `components/ui/` (shadcn new-york, **dựng từ Radix đã cài — 0 dependency UI mới**): `button`, `card`, `input`,
  `scroll-area` + KB-4.8 thêm `sheet`, `tooltip`, `toast`, `badge`, `separator`, `skeleton`, `slider`, `label`, `avatar`.
- **Theme** (KB-4.8): `lib/theme.ts` thuần (`readStoredTheme`/`resolveTheme`/`nextThemeMode`/`applyThemeToDocument`),
  3 chế độ light/dark/system lưu `localStorage['kb.theme']`; `<html class="dark">` + `color-scheme`; script inline
  trong `<head>` (`THEME_INIT_SCRIPT`) chống FOUC; component đọc store bằng `useSyncExternalStore` (không `next-themes`).
- **Layout chrome** (KB-5.11): chat **full-width** (không còn cột sidebar), lịch sử trong `Sheet` trượt từ trái;
  **không** dùng đường kẻ trang trí (bỏ `Separator`/`border-r`/`border-b` header) — phân cấp bằng nền
  (`bg-muted/40`, active `bg-primary/10`).
- **Typography** (KB-4.8): class `.md-body` trong `globals.css` (heading/list/table/blockquote/inline-code/link),
  **không** dùng `@tailwindcss/typography` (Q2 chốt B — không thêm dep).
- **Render khi stream** (KB-5.6, trả TD-21): `message-with-citations` hiển thị **plain text** lúc `isStreaming`
  (0 lần parse markdown cho mỗi token) và render markdown **1 lần** khi `end` tới. Component bọc `memo` +
  `messageId` + `onCitationClick` ổn định (`useCallback` ở `page.tsx`) ⇒ message đã xong **không** render lại khi
  message khác đang stream. Đo bằng `tests/stream-render.test.tsx`: markdown render **300 → 0** (stream 300 token),
  message cũ **40 → 0**.
- `lib/`: `api.ts` (**API client duy nhất**, KB-4.1 — parse envelope lỗi + `request_id`; KB-4.4 thêm `streamChat()`
  + `STREAMING_ENABLED`), `sse.ts` (KB-4.4 — parser SSE thuần: frame `\n\n`, bỏ `: ping`, map `start/token/end/error`),
  `errors.ts` (map `code` → message tiếng Việt + `retryable`), `types.ts` (thêm `ChatRequest/Response/Source/Metadata`),
  `utils.ts`, `export-utils.ts`, `rbac.ts` (chưa dùng).
- Gọi backend: qua `lib/api.ts` (`apiFetch`/`postChat`/**`streamChat`**) — **không** còn `fetch` inline trong `page.tsx`;
  banner lỗi `role="alert"` theo `error.code` + `request_id` + nút **Thử lại**.
- **Lịch sử hội thoại** (KB-4.9): `lib/chat-store.ts` = store ngoài React (in-memory + `localStorage['kb.chat_sessions']`,
  tối đa 50 session, ghi **debounce 300ms**), đọc bằng `useSyncExternalStore` (`getServerSnapshot` rỗng ⇒ không lệch
  hydration). Mỗi session giữ `messages` + `conversation_id` **riêng** (bản KB-4.1 dùng 1 key toàn cục `kb.conversation_id`
  — có migrate). Title session sinh từ câu hỏi đầu tiên. `ChatMessage` khai báo ở `lib/types.ts`.
  `sources` giữ nguyên **per chunk** (KB-4.3 — không dedup `file_path`, trả **TD-12**);
  chip `[S#]` → `citationFocus` ở `page.tsx` → `SourcesPanel` scroll + highlight card đúng `citation_id`.
- **Streaming mặc định** (KB-4.4): `POST /chat/stream` → `start → token* → (end | error)`, heartbeat `: ping` bị bỏ;
  nút **Stop** (`AbortController`) huỷ request nhưng **giữ** phần đã nhận; `NEXT_PUBLIC_STREAMING=false` ⇒ quay lại
  `/chat` blocking.
- **Kho tài liệu** (KB-4.5): drawer từ header gọi `/documents/status`, `/documents/folder-info`, `/ready`
  (503 vẫn đọc payload), `POST /documents/refresh` (timeout 30 phút), `DELETE /documents/clear` (gõ `CLEAR`).
- **Không có** route handler (`app/api/**/route.ts` = 0) dù `feedback-modal` gọi `POST /api/feedback/submit`.
- Chưa có `.env.example`? → có (KB-4.1); **lint/test**: `eslint.config.mjs` (flat, `eslint-config-next`) + `vitest.config.ts`
  (jsdom) + `tests/` (6 file, 50 test); `npm run test|lint|typecheck`; `next.config.mjs` **`ignoreBuildErrors: false`**
  (KB-4.6 — build type-check thật).
- `Dockerfile` multi-stage (non-root `appuser` uid 10001) + `HEALTHCHECK` (`node -e fetch`, vì `node:20-slim` không có
  `curl`); `ARG NEXT_PUBLIC_API_PROXY_URL`/`NEXT_PUBLIC_STREAMING` nhúng **lúc build**; `.dockerignore` (KB-4.7).
  Compose ở repo BE build FE từ `../Knowledge-base-fe` với `build.args`, **không** mount source, chờ BE `healthy`.

Việc còn lại → `Backlog.md` Phase 4 (breakdown 2026-11-08): **KB-4.1** API client + error/loading UX →
**KB-4.2** markdown GFM + chip `[S1]` → **KB-4.3** sources panel đúng `citation_id` (TD-12) → **KB-4.4** streaming
SSE → **KB-4.5** documents/health panel → **KB-4.6** quality gate + dọn leftover → **KB-4.7** Docker FE.

---

## 6. LLM provider & embeddings

- **LLM**: `ChatOpenAI` (chuẩn OpenAI-compatible). Hiện dùng **Groq** (free tier).
  Đổi provider = đổi 3 env (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`) — **không** sửa code.
  Xem ADR `docs/adr/0001-llm-provider-groq.md`.
- **Embeddings**: `Qwen/Qwen3-Embedding-0.6B` (đa ngữ VN+EN, 1024-dim) chạy **local CPU** → miễn phí,
  private, không phụ thuộc API. Cấu hình qua env `EMBEDDING_MODEL`; **đổi model ⇒ phải re-index**
  (dimension khác). (Phần cứng local: i5-12600K / 32GB RAM / GTX 1050Ti 4GB → đủ cho embedding CPU.)
- **`float32` trên CPU** (KB-5.14, trả TD-14): model mặc định bf16 nhưng CPU **không có kernel bf16 nhanh** ⇒
  ép `EMBEDDING_TORCH_DTYPE=float32` (đo: 601 chunk **7,3 phút** vs ~22 phút, ~3×). Đổi dtype cũng là
  "đổi không gian vector" ⇒ **phải re-index toàn bộ** (`DELETE /documents/clear` → `POST /documents/sync`).
- **Rate limit** (KB-5.15, TD-20): sliding window theo IP, **chỉ** `/chat` + `/chat/stream`, cờ
  `RATE_LIMIT_ENABLED` **TẮT** mặc định (bật cùng `AUTH_ENABLED` khi mở LAN/VPS); 429 + `Retry-After`.
  In-process ⇒ nhiều worker thì mỗi worker đếm riêng (TD-17).
- **Index sync lúc khởi động chạy nền** (KB-5.16, TD-25): `StartupSyncState` + `asyncio.create_task`
  (`STARTUP_SYNC_BACKGROUND=true`) ⇒ app phục vụ ngay, tiến trình xem ở `/ready` (`checks.startup_sync`) và
  `/documents/status`. Lỗi sync không làm chết app (chat dùng index cũ — nguyên tắc KB-5.1/KB-4.10).


---

## 7. Bảo mật PII (privacy-first)

> **Vì sao** che ở cổng ra (và vì sao ingest redaction để off): ADR
> [`0007`](docs/adr/0007-pii-redaction-o-cong-ra.md).


Chi tiết rule: `.clinerules/30-pii-safety.md`. Tóm tắt:

- Che **PII** (email, sđt, CCCD, số TK, địa chỉ) và **secret** (mật khẩu, key, JWT, PEM) **trước khi**
  gửi LLM, và tốt nhất cả trước khi **index** vào vector store.
- Cổng chặn: `PIIRedactor` gọi trong `ChatService` (và tuỳ chọn `DocumentService`).
- Đây là **yêu cầu cấp P0**, làm trước feature.

---

## 8. Roadmap phases

| Phase | Chủ đề | Trạng thái |
|---|---|---|
| **0** | Foundation & AI workflow: AI assets, chuyển sang Groq, hygiene config | ✅ Done |
| **1** | **Safety**: PII/secret redaction trước khi gửi LLM | ✅ Done |
| **2** | RAG quality: dedup, grounding, citations, tune params | ✅ Done (KB-2.1..2.5 — xem `docs/phases/phase-2.md`) |
| **3** | Backend robustness: error handling, tests, streaming ổn định | ✅ Done (KB-3.1 → 3.5 — xem `docs/phases/phase-3.md`) |
| **4** | Frontend/UX: markdown render, wire API, Docker FE | ✅ Done (KB-4.1 → 4.7 — `docs/phases/phase-4.md`) |
| **4b** | UI/UX overhaul: design system, dark mode, bỏ control giả, streaming UX | ✅ Done (KB-4.8 → 4.11 — `docs/phases/phase-4b.md`) |
| **5** | Nâng cao: upload tài liệu, latency, lịch sử bền, chất lượng truy hồi, auth, CI | Todo (breakdown xong: KB-5.1..5.7 — chờ trả lời Q&A) |
| **6** | **Tech refresh**: pin deps, Python bump, embedding/reranker **đa ngữ** | ✅ Done |
| **7** | Dev env: migrate sang WSL (Windows giữ tối thiểu) | ✅ Done |

> Phase xa chỉ ở mức **epic**; breakdown chi tiết khi tới lượt (`AGENTS.md` §3.1).
>
> **Phase 2 (breakdown 2026-11-07)** — KB-2.1 eval harness + baseline → KB-2.2 dedup chunk + áp
> `SIMILARITY_THRESHOLD` + chunk ID ổn định → KB-2.3 citation `[S1]` + grounding prompt → KB-2.4 chunking
> theo heading + re-index (**TD-7**) → KB-2.5 tune params (**TD-8**). Chi tiết + Q&A: `Backlog.md` §4.
>
> **Phase 4b (Done 2026-11-08)** — KB-4.8 design system + dark mode → KB-4.9 multi-conversation client-side + bỏ control giả → KB-4.10 mount folder tài liệu + guard refresh (lỗi mất index) → KB-4.11 streaming UX (pha truy hồi/đang viết + answer rỗng). Chi tiết: `docs/phases/phase-4b.md`.
>
> **Phase 3 (Done 2026-11-08)** — KB-3.1 error taxonomy + `X-Request-ID` → KB-3.2 retry/timeout/concurrency
> cho provider → KB-3.3 SSE contract + heartbeat + disconnect → KB-3.4 `/health` + `/ready` → KB-3.5 test
> tầng HTTP (trả **TD-4**). Chi tiết: `docs/phases/phase-3.md`.

---

## 9. Glossary

| Thuật ngữ | Nghĩa trong dự án |
|---|---|
| RAG | Retrieval-Augmented Generation — truy hồi tài liệu rồi mới sinh câu trả lời |
| Chunk | Một đoạn tài liệu nhỏ được embed + lưu vào vector store |
| Embedding | Vector biểu diễn ngữ nghĩa của text (local, mpnet-base-v2) |
| Hybrid retrieval | Kết hợp dense (vector) + sparse (BM25) |
| Re-ranking | Chấm lại điểm các chunk bằng cross-encoder |
| PII | Personally Identifiable Information — thông tin định danh cá nhân |
| Redaction | Thay PII/secret bằng placeholder trước khi gửi ra ngoài |
| Free tier | Hạn mức miễn phí của provider (Groq: 30 RPM · 1K req/ngày · 200K token/ngày) |

---

## 10. Tech stack assessment (2026-11)

Soát version/model thực tế vs khuyến nghị 2026. Việc khắc phục: `Backlog.md` **Phase 6** (KB-6.1..6.4).

| Hạng mục | Hiện tại | Chuẩn 2026 | Nhận xét |
|---|---|---|---|
| Python runtime | ✅ **3.13** (Dockerfile, KB-6.1) · 3.12 (local) | 3.13/3.14 (bugfix); 3.10 **EOL 2026-10** | ✅ đã bump |
| FastAPI / pydantic / pydantic-settings | 0.123 / 2.12 / 2.12 | current | ✅ |
| LangChain (`langchain*` split) | langchain 1.1 · langchain-openai 1.1 · community 0.4 | current | ✅ |
| OpenAI SDK | 2.8.1 | current | ✅ |
| ChromaDB | 1.3.5 | current | ✅ |
| `requirements.txt` pin | ✅ **range pin** `>=floor,<next-major` (KB-6.1) | — | ✅ đã pin |
| **Embedding model** | ✅ `Qwen/Qwen3-Embedding-0.6B` (đa ngữ, 1024-d) (KB-6.2) | `Qwen/Qwen3-Embedding-0.6B` / `google/embeddinggemma-300m` (đa ngữ) | ✅ đã đổi sang đa ngữ |
| **Reranker** | ✅ `BAAI/bge-reranker-v2-m3` (đa ngữ, Apache-2.0) (KB-6.3) | `BAAI/bge-reranker-v2-m3` (đa ngữ) | ✅ đã đổi sang đa ngữ |
| rank-bm25 (sparse) | cài | ổn | ✅ |
| FE: Next / React / Tailwind / TS | 16 / 19.2 / 4 / 5 | current | ✅ |
| FE: dep pin | ✅ đã pin (`latest`→version cụ thể) (KB-6.4) | — | ✅ |
| **Dev environment** | ✅ **WSL2 Ubuntu 26.04** · Python 3.13.18 (`uv`) · Node 26.13.0 LTS (`fnm`) · Docker 29.9.2 (KB-7.1) | Linux FS + toolchain user-space | ✅ đã migrate |

Nguồn: Python devguide (`devguide.python.org/versions`, 2026) · BentoML embedding guide (2026) ·
recal reranker guide (2026).

> **Điểm "outdate" quan trọng nhất**: embedding + reranker đều **English-only** trong khi KB có tài liệu
> **tiếng Việt** → retrieval tiếng Việt kém. Ưu tiên xử lý (KB-6.2, KB-6.3) trước khi tối ưu RAG (Phase 2).


