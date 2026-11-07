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
  - `SIMILARITY_THRESHOLD` (default: `0.7`)
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

- There are currently no automated tests in this repository. TODO: Add unit and integration tests for services and API endpoints.

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
