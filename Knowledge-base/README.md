# RAG Chatbot API

Retrieval-Augmented Generation (RAG) chatbot API for asking questions over your project documentation and files.

This README consolidates the current, working setup based on the repository source. Outdated info from the previous README has been corrected. Unknown or unverified items are marked as TODO.

## Overview

- Loads documents from `documents/` into a ChromaDB vector store
- Retrieves relevant context and chats via OpenAI-compatible LLMs
- Optional query rewrite, hybrid retrieval (dense + BM25), and re-ranking
- Configurable system prompt from file
- Run locally or with Docker/Docker Compose

## Tech Stack

- Language: Python 3.13
- Framework: FastAPI (served by Uvicorn)
- RAG: LangChain, ChromaDB, sentence-transformers, BM25 re-ranking
- Packaging: `requirements.txt` (pip)
- Containerization: Docker, docker-compose

## Requirements

- Python 3.13+
- pip
- Docker and Docker Compose (optional, for containerized run)

## Quickstart (Docker Compose)

Sau **KB-4.7**, `docker compose up` chạy **2 service**: `chatbot-api` (BE :8000) + `chatbot-ui` (FE :3000).

1) Copy `.env.example` to `.env` and update values.

2) (Tuỳ chọn) đổi URL mà **browser** dùng để gọi BE — `NEXT_PUBLIC_*` nhúng vào bundle **lúc build**:

```bash
# mặc định http://localhost:8000 (browser trên máy host gọi BE)
export NEXT_PUBLIC_API_PROXY_URL=http://localhost:8000
# tắt streaming SSE khi build FE
export NEXT_PUBLIC_STREAMING=false
```

3) Start cả BE + FE:

```bash
docker compose up -d --build
docker compose ps            # cả 2 service phải "healthy"
```

4) Mở:

- FE: http://localhost:3000 (panel **Kho tài liệu** ở header để xem index/readiness)
- API docs: http://localhost:8000/docs

Ghi chú vận hành:

- `chatbot-ui` **không** mount source nữa (image là thứ sẽ deploy); FE chờ BE `healthy` mới start
  (`depends_on: condition: service_healthy`).
- `chatbot-api` chạy bằng **UID/GID của bạn** (`USER_ID`/`GROUP_ID`, mặc định `1000`) vì `./chroma_db` là bind mount
  của user trên host — nếu image chạy uid 10001 (mặc định trong Dockerfile) thì ChromaDB báo
  `attempt to write a readonly database`.
- Model embedding/reranker nằm trong **named volume** `hf-cache` (~3.3GB). Lần `up` đầu tiên phải tải model
  ⇒ `start_period` của healthcheck là **600s**. Muốn nhanh: copy sẵn cache từ máy:
  ```bash
  docker volume create knowledge-base_hf-cache
  docker run --rm -v knowledge-base_hf-cache:/dst -v ~/.cache/huggingface:/src:ro busybox \
    sh -c 'cp -a /src/. /dst/'
  ```
- Đổi code BE/FE ⇒ `docker compose up -d --build` lại (không còn hot-reload qua mount).

## Local Setup (without Docker)

1) Python environment (dev chuẩn: **WSL2 Ubuntu** — `AGENTS.md` §6, KB-7.1)

- Create and activate a virtual environment.
  - PowerShell (Windows):
    ```powershell
    python -m venv .venv; .\.venv\Scripts\Activate.ps1
    ```
  - macOS/Linux:
    ```bash
    python3 -m venv .venv && source .venv/bin/activate
    ```

2) Install dependencies

```bash
uv pip install -r requirements.txt -r requirements-dev.txt
```

> Code đặt trên Linux FS (`~/projects/kb-khoa-hoc`), **không** dùng `/mnt/c|/mnt/d` (chậm với `torch`).

3) Configure environment

- Create `.env` in the project root (use `.env.example` as a starting point).

4) Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000/docs

5) Run tests

```bash
.venv/bin/python -m pytest -q     # 19 passed
```

## How it Loads and Chats with Documents

- On startup, if `AUTO_LOAD_ON_STARTUP=true`, the app recursively reads files under `DOCUMENTS_FOLDER` (default `./documents`) and indexes supported files into ChromaDB at `CHROMA_DB_PATH` (default `./chroma_db`).
- During chat, it retrieves relevant chunks (`RETRIEVAL_K`, hybrid/BM25 if enabled), optionally re-ranks, builds context, and sends messages to the selected LLM.

## API Endpoints

From `app/main.py`:

- `GET /` — Health/info (returns status, message, version)
- `POST /chat` — Chat with the RAG system
- `POST /chat/stream` — Chat with server-sent events (SSE) streaming

### SSE contract (KB-3.3)

`POST /chat/stream` stream về theo thứ tự **`start → token* → (end | error)`** — luôn có đúng **một** event
kết thúc, không bao giờ cắt ngang.

```text
data: {"type": "start", "conversation_id": "...", "metadata": {...}}

data: {"type": "token", "token": "Xin "}

: ping

data: {"type": "end", "answer": "...", "sources": [...], "metadata": {...}}
```

- Event `error` dùng **cùng schema** envelope lỗi của `/chat`:
  `{"type": "error", "error": {"code", "message", "request_id"}}` (`request_id` = header `X-Request-ID`).
- Lỗi xảy ra **sau** khi đã stream ⇒ HTTP vẫn `200` (header đã gửi), client dựa vào event `error`.
- **Heartbeat**: comment `: ping` nếu quá `SSE_HEARTBEAT_SECONDS` (default 15) không có event — giữ kết nối
  qua proxy/idle timeout khi LLM chậm. Client SSE bỏ qua comment an toàn.
- Header chống buffer/tắt cache: `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`.
- **Client disconnect** (đóng tab, `curl` timeout): generator dừng ngay, log mức `info` (không stack). Phần đã
  trả lời **được giữ** trong history nếu đã phát ≥1 token, kèm `interrupted: true`; chưa có token thì bỏ.

### Health & readiness (KB-3.4)

| Endpoint | Vai trò | Chi phí |
|---|---|---|
| `GET /health` | **liveness** — process còn sống ⇒ luôn `200` | rẻ: không chạm Chroma/provider |
| `GET /ready` | **readiness** — đủ điều kiện trả lời? | rẻ: 3 check `provider_config` / `prompt_file` / `collection` |
| `GET /ready?deep=true` | thêm check **gọi provider thật** (`max_tokens=1`) | tốn 1 request ⇒ mặc định **tắt**, chỉ dùng tay |

```json
GET /health  →  {"status": "ok", "version": "1.0.0", "uptime_seconds": 12.34}

GET /ready   →  200
{
  "status": "ok",
  "checks": {
    "provider_config": {"ok": true,  "detail": "model=openai/gpt-oss-120b"},
    "prompt_file":     {"ok": true,  "detail": "prompt file: system_prompt.txt"},
    "collection":      {"ok": true,  "detail": "601 chunks indexed"}
  }
}
```

- `ok` (200) — dùng được đầy đủ.
- `degraded` (200) — thiếu tài liệu (collection rỗng/lỗi): vẫn chat được, trả lời "không có trong knowledge base".
- `error` (**503**) — thiếu cấu hình provider (`OPENAI_API_KEY`/`OPENAI_MODEL`/`OPENAI_BASE_URL`) hoặc thiếu
  file prompt; hoặc `deep=true` mà provider không trả lời.
- Response của `/ready` dùng body riêng (`status` + `checks`), **không** dùng envelope `{"error": ...}` của API
  — vì đây là probe cho orchestrator, không phải response nghiệp vụ. `checks.*.detail` không chứa secret/`str(e)`.
- Docker image có `HEALTHCHECK` trỏ `/health` (`--start-period=180s` vì lần đầu tải embedding model).

```bash
curl -s localhost:8000/health
curl -s localhost:8000/ready
curl -s "localhost:8000/ready?deep=true"   # kiểm key/provider thật (tốn 1 request)
```
- `POST /documents/refresh` — Clear and re-load from `DOCUMENTS_FOLDER`
- `GET /documents/folder-info` — Inspect the docs folder and supported file counts
- `GET /documents/status` — Status of the document store
- `DELETE /documents/clear` — Clear all indexed documents

OpenAPI docs: http://localhost:8000/docs

### Error contract (KB-3.1)

Mọi response lỗi dùng **một** envelope duy nhất (`app/core/errors.py`):

```json
{
  "error": {
    "code": "provider_rate_limited",
    "message": "The language model provider rate limit was reached. Please retry later.",
    "request_id": "19e63b57-00f9-4def-ac48-3f357ae0e79a"
  }
}
```

- `code` là **hằng số** → client switch theo `code`, đừng parse `message`.
- `message` là message **chung**, không chứa chi tiết nội bộ. Chi tiết kỹ thuật (`str(e)`, host
  provider, path, traceback) **chỉ** nằm trong log — tra bằng `request_id`.
- `request_id` = header `X-Request-ID`. Client được gửi `X-Request-ID` của mình (chỉ `[A-Za-z0-9._-]`,
  ≤ 64 ký tự, id không hợp lệ sẽ bị thay bằng uuid4) và server trả lại đúng id đó trong header + body lỗi.

| code | HTTP | Khi nào |
|---|---|---|
| `validation_error` | 422 | body sai; kèm `error.details[]` = `loc`/`msg`/`type` (**không** echo giá trị client gửi) |
| `not_found` | 404 | route/tài nguyên không tồn tại |
| `method_not_allowed` | 405 | sai HTTP method |
| `bad_request` / `forbidden` / `payload_too_large` | 400 / 403 / 413 | lỗi request phía framework |
| `provider_auth_failed` | 502 | provider từ chối credential |
| `provider_rate_limited` | 429 | provider hết quota/rate limit (Groq TPM) |
| `provider_unavailable` | 503 | không gọi được provider (mạng/hạ tầng) |
| `provider_timeout` | 504 | provider không trả lời kịp |
| `service_unavailable` | 503 | service (chat/document) chưa khởi tạo xong |
| `document_store_error` | 500 | lỗi thao tác trên vector store/tài liệu |
| `internal_error` | 500 | lỗi không phân loại (stack chỉ ở log) |

`POST /chat/stream` (SSE) giữ event `{"type": "error", "code", "message"}` với cùng ngữ nghĩa
`code`/`message`; event `error` đầy đủ (kèm `request_id`) nằm ở KB-3.3.

## Environment Variables

Defined in `app/core/config.py`. All can be provided via `.env`.

- OpenAI
  - `OPENAI_API_KEY` (required)
  - `OPENAI_BASE_URL` (required in most setups; see note below)
  - `OPENAI_MODEL` (default: `gpt-3.5-turbo`)
  - `OPENAI_EMBEDDING_MODEL` (default: `text-embedding-ada-002`)
  - `OPENAI_API_TYPE` (default: `openai`)
  - `OPENAI_API_VERSION` (default: `2023-05-15`)

- ChromaDB
  - `CHROMA_DB_PATH` (default: `./chroma_db`)
  - `COLLECTION_NAME` (default: `documents`)

- Document Processing
  - `CHUNK_SIZE` (default: `1000`)
  - `CHUNK_OVERLAP` (default: `200`)
  - `MAX_FILE_SIZE_MB` (default: `10`)
  - `EMBEDDING_BATCH_SIZE` (default: `64`)

- Documents Folder
  - `DOCUMENTS_FOLDER` (default: `./documents`)
  - `AUTO_LOAD_ON_STARTUP` (default: `true`)

- RAG Retrieval and Ranking
  - `RETRIEVAL_K` (default: `5`)
  - `SIMILARITY_THRESHOLD` (default: `0.0` = off) — cosine floor cho **dense candidates**; không áp cho
    score hybrid/rerank. Đặt số khi chưa đo sẽ mất recall (0.7 từng làm `hit@k` 0.933 → 0.333), xem KB-2.5.
  - `DEDUP_ENABLED` (default: `true`) — bỏ chunk gần trùng nội dung trước khi cắt top-k
  - `DEDUP_JACCARD_THRESHOLD` (default: `0.8`) — ngưỡng Jaccard shingle 3-gram để coi là "gần trùng"
  - `MAX_CHUNKS_PER_FILE` (default: `2`, `0` = off) — tối đa số chunk cùng 1 file trong top-k
  - `ENABLE_BM25` (default: `true`)
  - `ENABLE_HYBRID` (default: `true`)
  - `HYBRID_ALPHA` (default: `0.5`)
  - `HYBRID_CANDIDATE_K` (default: `20`)
  - `ENABLE_RERANK` (default: `true`)
  - `RERANK_TOP_N` (default: `20`)
  - `RERANK_MODEL` (default: `BAAI/bge-reranker-v2-m3`)

- Chat
  - `DEFAULT_TEMPERATURE` (default: `0.7`)
  - `DEFAULT_MAX_TOKENS` (default: `1000`)
  - `MAX_CONVERSATION_LENGTH` (default: `10`)

- Provider resilience (KB-3.2) — Groq free tier chỉ có **TPM 8000**
  - `PROVIDER_TIMEOUT_SECONDS` (default: `60`) — timeout của **một** call tới provider (đẩy vào SDK).
  - `PROVIDER_MAX_RETRIES` (default: `2`) — số lần retry cho `429` / `5xx` / timeout / lỗi kết nối
    (≈ tối đa 6s chờ với base 2s). `4xx` khác **không** retry. `ChatOpenAI(max_retries=0)` nên SDK
    không retry — service là tầng retry duy nhất.
  - `PROVIDER_RETRY_BASE_DELAY` (default: `2.0`) — base cho exponential backoff + **jitter** (`1–2s`, `2–4s`, …);
    header `Retry-After` của provider (giây **hoặc** ms) được ưu tiên, cap ở `PROVIDER_TIMEOUT_SECONDS`.
  - `PROVIDER_MAX_CONCURRENCY` (default: `1`) — số call provider đồng thời; `1` = **serialize** để 2 request
    cùng lúc không đẩy TPM vượt hạn mức (query rewrite cũng đi qua cổng này, nhưng **không** retry).

- SSE (KB-3.3)
  - `SSE_HEARTBEAT_SECONDS` (default: `15`) — gửi comment `: ping` nếu quá N giây không có event, để
    proxy/idle timeout không cắt stream khi LLM chậm.

- Prompt Files
  - `SYSTEM_PROMPT_PATH` (default: `./prompts/system_prompt.txt`)
  - `REWRITE_SYSTEM_PROMPT_PATH` (default: `./prompts/rewrite_system_prompt.txt`)

- Supported File Extensions
  - `SUPPORTED_EXTENSIONS` — optional override for allowed extensions.
    - Default in code: `[".md", ".docx", ".pdf", ".txt", ".json"]`
    - Example in `.env.example`: `[".py", ".md", ".txt", ".json", ".yaml", ".yml", ".rst", ".docx", ".pdf"]`

Note on `OPENAI_BASE_URL`:
- The code expects it via env, but also initializes settings with an empty string for startup resilience. In practice, set a correct base URL (or use the default OpenAI endpoint for your chosen SDK/provider) to avoid runtime errors.

## Prompts Configuration

You can configure prompts via files instead of hard-coding:

1) Create folder:

```
prompts/
```

2) Create `prompts/system_prompt.txt` (may include `{context}` placeholder):

```
Bạn là trợ lý onboarding cho dự án RAG Chatbot API.\n
══════════════════════════════════════════
NGỮ CẢNH LIÊN QUAN TỪ TÀI LIỆU:
══════════════════════════════════════════
{context}

Hướng dẫn trả lời:
- Trả lời ngắn gọn, có trích dẫn file/đường dẫn khi có thể
- Giải thích các thuật ngữ kỹ thuật khi cần
```

3) Optional: `prompts/rewrite_system_prompt.txt` for the query rewrite step (no placeholders required):

```
You are a query reformulation assistant for a RAG system.
Rewrite the user's query to better retrieve relevant documentation.
Guidelines:
- Be concise (5-25 words).
- Expand with key technical terms when helpful.
- Do NOT answer; output only the rewritten query.
```

4) Add paths in `.env`:

```env
SYSTEM_PROMPT_PATH=./prompts/system_prompt.txt
REWRITE_SYSTEM_PROMPT_PATH=./prompts/rewrite_system_prompt.txt
```

Notes:
- If the files are missing or cannot be read, the app falls back to built-in prompts.
- Docker mounts the project into the container (`.:/app`), so keep the `prompts/` folder in the project root.

## Running and Scripts

- Uvicorn (local): `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Dockerfile entrypoint: Uvicorn command above
- Docker Compose services (KB-4.7): `chatbot-api` (BE, `8000:8000`) + `chatbot-ui` (FE, `3000:3000`)
  - BE volumes: `./chroma_db:/app/chroma_db`, `hf-cache:/hf-cache` (named volume, chứa model HF)
  - FE: build từ `../Knowledge-base-fe` với `build.args` (`NEXT_PUBLIC_API_PROXY_URL`, `NEXT_PUBLIC_STREAMING`),
    **không** mount source, `depends_on: chatbot-api (service_healthy)`

Common commands:
- Build and run: `docker compose up -d --build` (lần đầu tải model ~3.3GB ⇒ FE chỉ start khi BE healthy)
- Trạng thái/health: `docker compose ps`
- Stop: `docker compose down` (thêm `-v` nếu muốn xoá luôn volume `hf-cache`)
- Logs: `docker compose logs -f chatbot-api` hoặc `chatbot-ui`

## Project Structure

```
knowledge-base/
├─ app/
│  ├─ core/
│  │  └─ config.py
│  ├─ models/
│  │  └─ schemas.py
│  ├─ services/
│  │  ├─ chat_service.py
│  │  └─ document_service.py
│  └─ main.py
├─ chroma_db/              # Vector DB (created/populated at runtime)
├─ documents/              # Place your source docs here
├─ prompts/
│  ├─ system_prompt.txt
│  └─ rewrite_system_prompt.txt
├─ .env                    # Your environment variables (not committed)
├─ .env.example
├─ requirements.txt
├─ docker-compose.yml
└─ Dockerfile
```

## Testing

- Unit/integration tests live in `tests/` (PII redaction, ingest redaction, embedding config,
  error contract + `X-Request-ID` trong `tests/test_error_contract.py`). Run:
  ```bash
  .venv/bin/python -m pytest -q
  ```
- Retrieval/answer quality is measured by the eval harness (see below), not by unit tests.

### Test API (KB-3.5 — trả TD-4)

Test tầng HTTP dùng `TestClient` + **fake service** qua `app.dependency_overrides`: không load model,
không mở ChromaDB, không gọi mạng, **không chạy lifespan** ⇒ chạy offline, rất nhanh.

```bash
cd Knowledge-base
.venv/bin/python -m pytest tests/test_api_endpoints.py tests/test_api_errors.py tests/test_api_stream.py -q
# 28 passed in 0.13s
```

| File | Bảo vệ contract |
|---|---|
| `tests/conftest.py` | fixture `api_client` (override `get_chat_service` / `get_document_service`), fake service, `health_service_factory` |
| `tests/test_api_endpoints.py` | happy path: `/`, `/health`, `/ready` (ok / degraded / error), `/chat`, `/documents/status\|refresh\|clear\|folder-info` |
| `tests/test_api_errors.py` | envelope `{"error": {code, message, request_id}}`: 422 / 404 / 405 / 429 / 502 / 503 / 504 / 500, echo `X-Request-ID`, **không lộ** `str(e)` / URL provider / traceback |
| `tests/test_api_stream.py` | SSE: `start → token* → end`, event `error` + `request_id`, header chống buffer |

Toàn bộ suite: `.venv/bin/python -m pytest -q` (**164 passed**, ~1s).

## Đo chất lượng RAG (eval harness)

Bộ đo chất lượng retrieval + grounding, dùng làm baseline cho Phase 2 (`Backlog.md` KB-2.1).
Chạy từ thư mục `Knowledge-base/`:

```bash
# 1) (Tuỳ chọn) index lại DOCUMENTS_FOLDER — cần collection trước khi đo
.venv/bin/python eval/run_eval.py --build-index --limit 1

# 2) Đo retrieval — KHÔNG gọi LLM, không tốn quota
.venv/bin/python eval/run_eval.py --mode retrieval --tag baseline
.venv/bin/python eval/run_eval.py --mode retrieval --rerank off   # bỏ qua reranker (nhanh, không tải model 2.3GB)

# 3) Đo câu trả lời thật qua Groq (/chat) — tốn 1 request/câu
.venv/bin/python eval/run_eval.py --mode full --tag baseline
```

Bộ câu hỏi vàng: `eval/qa_set.json` (`question`, `expected_files`, `expected_keywords`).
Kết quả in ra bảng markdown + snapshot JSON ở `eval/runs/`.

| Metric | Ý nghĩa | Mode |
|---|---|---|
| `hit_at_k` | tỉ lệ câu có >= 1 `expected_file` nằm trong top-k | retrieval |
| `mrr` | mean reciprocal rank của file kỳ vọng đầu tiên | retrieval |
| `dup_ratio` | tỉ lệ cặp chunk trong top-k gần trùng (Jaccard shingle 3-gram >= 0.8) | retrieval |
| `precision_at_k` | tỉ lệ hit trong top-k trỏ đúng file kỳ vọng (precision của ngữ cảnh) | retrieval |
| `distinct_file_ratio` | tỉ lệ file khác nhau trong top-k (1.0 = không lặp file; 0.2 = 5 hit cùng 1 file) | retrieval |
| `latency_p50` | trung vị thời gian 1 query (giây) | cả hai |
| `citation_presence` | tỉ lệ câu trả lời có nhãn `[S1]`, `[S2]`, … (bất kỳ đâu) | full |
| `inline_citation_presence` | tỉ lệ câu trả lời có nhãn **trong thân bài** (không chỉ dòng `Nguồn:` cuối) | full |
| `answer_keyword_hit` | tỉ lệ câu trả lời chứa keyword kỳ vọng | full |

Flag hữu ích: `--limit N` (chạy thử N câu), `--k N` (override `RETRIEVAL_K`),
`--rerank {env,on,off}` (override `ENABLE_RERANK`), `--sleep N` (nghỉ giữa các câu ở `--mode full`
để không bị Groq `429` TPM), `--tag` (nhãn snapshot).

> Lưu ý PII: `--mode full` gửi câu hỏi + context lên LLM provider. Context đi qua `PIIRedactor`
> trước khi ra ngoài, nhưng tài liệu vẫn là note cá nhân → cân nhắc trước khi chạy.

## Troubleshooting

- Packages missing locally: ensure your venv is active and run `pip install -r requirements.txt`.
- Connection issues:
  - Verify `OPENAI_API_KEY` and `OPENAI_BASE_URL`
  - Check network access to your endpoint
- Reduce telemetry/noise in containers: the Dockerfile already sets env vars to disable Chroma and LangChain telemetry.

## License

TODO: Add a license file and specify the license here.

## Acknowledgements

- FastAPI, LangChain, ChromaDB, sentence-transformers, and related open-source projects.
