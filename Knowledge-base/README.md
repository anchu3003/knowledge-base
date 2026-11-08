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

1) Copy `.env.example` to `.env` and update values.

2) Start the API:

```bash
docker compose up -d --build
```

3) Open API docs:

- http://localhost:8000/docs

Default container name: `rag-chatbot-api` (from `docker-compose.yml`).

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
- Docker Compose service: `rag-chatbot-api`
  - Ports: `8000:8000`
  - Volumes: `.:/app`, `./chroma_db:/app/chroma_db`

Common commands:
- Build and run: `docker compose up -d --build`
- Stop: `docker compose down`
- Logs: `docker compose logs -f rag-chatbot-api`

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
