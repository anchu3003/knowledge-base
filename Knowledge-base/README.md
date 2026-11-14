# RAG Chatbot API — Knowledge base cá nhân (backend)

FastAPI + LangChain + ChromaDB + Qwen3-Embedding + rerank cross-encoder local, sinh câu trả lời bằng
**Groq** (OpenAI-compatible). Đây là **backend**; UI ở repo [`Knowledge-base-fe`](../Knowledge-base-fe/README.md),
tổng quan hệ thống ở [`../README.md`](../README.md).
> Link dạng `../` (`../docs/adr/`, `../Knowledge-base/`, `../README.md`) chỉ mở được khi workspace có đủ
> root + 2 repo cạnh nhau (đúng cách repo này được dùng); trên GitLab chúng sẽ 404.


> Số liệu trong file này **tính đến 2026-11-10**: **320 test** · **601 chunk / 56 file** · image Docker
> **2,68 GB**. **Vì sao** các quyết định kiến trúc: [`../docs/adr/README.md`](../docs/adr/README.md) (17 ADR).

## Overview

- **Index tăng dần**: so `sha256(nội dung file)` với index, chỉ embed file mới/đổi (~1,2 s/file) — không
  clear index, chat vẫn trả lời trong lúc sync.
- **Hybrid retrieval**: dense (Qwen3-Embedding, local CPU) + BM25 (sparse trong Chroma), `HYBRID_ALPHA=0.5`.
- **Dedup + rerank**: gộp chunk gần trùng, cap 2 chunk/file, rerank `BAAI/bge-reranker-v2-m3` trên
  `RERANK_TOP_N=6` ứng viên (p50 **3,44 s**/câu trên bộ vàng 20 câu).
- **Streaming SSE** `start → token* → (end | error)` + heartbeat 15 s.
- **Lịch sử bền**: SQLite (`./data/chat.db`, WAL), redact PII **trước khi lưu**.
- **An toàn**: redaction PII ở cổng ra (mặc định BẬT); auth token tĩnh + rate limit per-IP (cả hai **mặc
  định TẮT**, bật khi mở LAN/VPS).

## Tech Stack

| Thành phần | Chọn | Vì sao (ADR) |
|---|---|---|
| API | FastAPI ≥ 0.123 (Python 3.13) | async, SSE dễ, Pydantic schema |
| LLM | Groq `openai/gpt-oss-120b` qua `ChatOpenAI` | free tier, nhanh — [ADR-0001](../docs/adr/0001-llm-provider-groq.md) |
| Vector store | ChromaDB ≥ 1.3 `PersistentClient` | nhúng, sparse native cho hybrid — [ADR-0002](../docs/adr/0002-vector-store-chromadb.md) |
| Embedding | `Qwen/Qwen3-Embedding-0.6B`, **float32**, CPU | đa ngữ VN+EN, private — [ADR-0003](../docs/adr/0003-embedding-model-qwen3.md) |
| Rerank | `BAAI/bge-reranker-v2-m3` (CrossEncoder, CPU) | chất lượng top-k — [ADR-0006](../docs/adr/0006-rerank-cross-encoder.md) |
| History | `sqlite3` stdlib + WAL | 0 hạ tầng — [ADR-0014](../docs/adr/0014-lich-su-chat-sqlite.md) |

## Requirements

- Docker + Docker Compose (khuyến nghị), **hoặc** Python **3.13** + `uv` (dev tay).
- RAM ~2 GB cho tiến trình (Qwen3 0.6B ~600 MB + reranker ~600 MB + Chroma).
- Disk: model HF ~3,3 GB (volume `hf-cache`, **không** bake vào image).
- `OPENAI_API_KEY` (Groq key) + `OPENAI_BASE_URL`.

## Quickstart (Docker Compose)

```bash
cd Knowledge-base
cp .env.example .env          # điền OPENAI_API_KEY + OPENAI_BASE_URL, KHÔNG commit .env
docker compose up -d --build  # lần đầu ~60-90 s (build) + tải model ~3,3 GB vào volume
docker compose ps             # chatbot-api phải "healthy"
```

| Cổng | Ý nghĩa |
|---|---|
| **8010** | API trên **máy host** (`8010:8000` — dời port để không trùng project khác) |
| 8000 | Port **trong container** (và port khi chạy uvicorn tay) |
| 8010/docs | Swagger UI |

Healthcheck nội bộ dùng `/health` (liveness — không chạm Chroma/provider, luôn 200 khi process sống).

## Local Setup (without Docker)

```bash
cd Knowledge-base
uv python install 3.13
uv venv --python 3.13 .venv
uv pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                       # điền key
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- Model HF tải lần đầu (~3,3 GB) vào `~/.cache/huggingface`; sau đó cache.
- **Không** dùng `--reload` khi đo eval/latency (reload làm nhiễu số đo).

## How it loads and chats with documents

```
Interview/*.md ──scan+hash──► SyncPlan(added/updated/removed)
        │                          │
        │                          ├─ added/updated → chunk (heading → size 1000/200) → embed (fp32) → Chroma
        │                          └─ removed       → xoá chunk theo metadata `source`
        ▼
   Chroma `documents` (601 chunk)  ──hybrid (dense+BM25)──► 20 ứng viên
        │                                                    │
        │                                    dedup + cap 2/file → rerank top-6
        │                                                    ▼
   question ─► multi-query split (≤3 part) ──────────► top-3 context (+ redact PII)
                                                             ▼
                                            Groq (gpt-oss-120b) → câu trả lời (+ sources)
```

## API Endpoints

| Method | Path | Mục đích | Khi nào dùng / ghi chú |
|---|---|---|---|
| GET | `/` | info API | smoke test |
| GET | `/health` | liveness | healthcheck Docker — **luôn 200** khi process sống |
| GET | `/ready` | readiness | `ok`/`degraded`/`error`; `?deep=true` gọi provider 1 request (`max_tokens=1`); có `checks.startup_sync` + `checks.rate_limit` |
| POST | `/chat` | hỏi 1 lần | trả `response` + `sources` + `metadata` |
| POST | `/chat/stream` | hỏi + SSE | `start → token* → (end\|error)`; heartbeat 15 s |
| GET | `/conversations` | list hội thoại | metadata (id, title, updated_at), lazy-load |
| GET | `/conversations/{id}` | chi tiết | messages đã redact |
| DELETE | `/conversations/{id}` | xoá hội thoại | 404 nếu không có |
| GET | `/documents/status` | trạng thái index | `document_count`, `index_version`, `rerank_cache`, `startup_sync` |
| GET | `/documents/folder-info` | thông tin folder | số file hỗ trợ, `exists`, danh sách (≤20) |
| POST | `/documents/sync` | **index tăng dần** | dùng hàng ngày — **không** xoá index |
| POST | `/documents/refresh` | clear + index lại | chỉ khi index hỏng; **~7,3 phút** (601 chunk, fp32) |
| DELETE | `/documents/clear` | xoá sạch index | không xoá file trên đĩa |

Guard: `/documents/sync` và `/documents/refresh` trả **409 `documents_folder_empty`** nếu folder không tồn
tại hoặc 0 file hỗ trợ (nếu không sẽ xoá sạch index — KB-4.10).

## Sync vs Refresh

| | `POST /documents/sync` | `POST /documents/refresh` |
|---|---|---|
| Cách làm | hash nội dung → chỉ embed file mới/đổi, xoá chunk của file đã bỏ | `clear_database()` rồi index lại toàn bộ |
| Thời gian | **~1,2 s/file** (không đổi gì: **0,03 s**) | **~7,3 phút** cho 601 chunk (fp32) |
| Chat trong lúc chạy | **vẫn trả lời** (index cũ còn) | **không** (index rỗng) |
| Rủi ro | thấp (guard folder rỗng) | cao nếu folder sai → mất index |
| Dùng khi | thêm/sửa/xoá file (hàng ngày, tự động lúc startup) | đổi `CHUNK_SIZE`/embedding/dtype, index hỏng |

Chi tiết vì sao: [ADR-0011](../docs/adr/0011-index-tang-dan-theo-hash.md).

## Lịch sử hội thoại (KB-5.2)

- SQLite tại `CHAT_DB_PATH` (mặc định `./data/chat.db`), `PRAGMA journal_mode=WAL` + `busy_timeout` ⇒ đọc
  trong lúc ghi, không hỏng file khi container bị kill.
- **Redact PII trước khi lưu** ⇒ reload có thể thấy `[REDACTED:email]` (trade-off có chủ ý — ADR-0007/0014).
- `MAX_CONVERSATIONS=200`: vượt thì xoá session cũ nhất.
- DB không mở được (quyền/volume) ⇒ app **vẫn chạy** với lịch sử in-memory, log warning.

## Environment Variables

Đối chiếu `app/core/config.py` (63 alias) ↔ `.env.example` bằng script (2026-11-10): **khớp 100%** sau khi
bỏ 2 biến chết (`APP_NAME`, `APP_VERSION` — không có alias ⇒ không có tác dụng) và thêm
`OPENAI_API_VERSION`.

**Bắt buộc**

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `OPENAI_API_KEY` | — | Groq key (dạng `gsk_…`) — **không** commit |
| `OPENAI_BASE_URL` | — | `https://api.groq.com/openai/v1` |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | thực dùng `openai/gpt-oss-120b` |

**Dữ liệu & index**

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `DOCUMENTS_FOLDER` | `Interview` | folder nguồn |
| `AUTO_LOAD_ON_STARTUP` | `true` | sync lúc khởi động |
| `STARTUP_SYNC_BACKGROUND` | `true` | sync chạy **nền** ⇒ app phục vụ ngay (KB-5.16) |
| `CHROMA_DB_PATH` / `COLLECTION_NAME` | `./chroma_db` / `documents` | |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `200` | đổi ⇒ phải `refresh` (hash không đổi theo tham số chunk) |
| `EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-0.6B` | đổi ⇒ re-index |
| `EMBEDDING_TORCH_DTYPE` | `float32` | **CPU nhanh hơn bf16 ~3–4×**; đổi ⇒ re-index (KB-5.14) |
| `EMBEDDING_BATCH_SIZE` | `64` | |
| `SUPPORTED_EXTENSIONS` | `.md,.docx,.pdf,.txt,.json` | |

**Retrieval & rerank**

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `RETRIEVAL_K` | `3` | số chunk đưa vào prompt |
| `ENABLE_BM25` / `HYBRID_ALPHA` / `HYBRID_CANDIDATE_K` | `true` / `0.5` / `20` | hybrid (ADR-0005) |
| `SIMILARITY_THRESHOLD` | `0.0` | **để 0**: score hybrid đã normalize (0,7 làm `hit@k` sụp — ADR-0005) |
| `DEDUP_ENABLED` / `DEDUP_JACCARD_THRESHOLD` / `MAX_CHUNKS_PER_FILE` | `true` / `0.8` / `2` | |
| `ENABLE_RERANK` / `RERANK_MODEL` | `true` / `BAAI/bge-reranker-v2-m3` | |
| `RERANK_TOP_N` | **`6`** | chốt bằng eval (ADR-0012): 20 → 9,7 s, 6 → 3,44 s, `MRR` như nhau |
| `RERANK_CACHE_ENABLED` / `RERANK_CACHE_TTL_SECONDS` / `RERANK_CACHE_MAX_ENTRIES` | `true` / `3600` / `256` | **tắt khi đo eval** |
| `MULTI_QUERY_ENABLED` / `MULTI_QUERY_MAX_PARTS` | `true` / `3` | heuristic split (ADR-0013) |

**Provider & streaming**

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `PROVIDER_MAX_CONCURRENCY` | **`1`** | tránh vượt TPM free tier (ADR-0008) |
| `PROVIDER_MAX_RETRIES` / `PROVIDER_RETRY_BASE_DELAY` | `2` / `2.0` | backoff + jitter, đọc `Retry-After` |
| `SSE_HEARTBEAT_SECONDS` | `15` | proxy idle timeout |

**An toàn / vận hành**

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `ENABLE_PII_REDACTION` | `true` | redact ở cổng ra (ADR-0007) |
| `PII_REDACT_INGEST` | `false` | bật ⇒ **lệch retrieval** (KB-1.2) |
| `AUTH_ENABLED` / `API_TOKEN` | `false` / — | token tĩnh, header `X-API-Key`; bật mà token rỗng ⇒ chặn tất cả |
| `RATE_LIMIT_ENABLED` / `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | `false` / `30` / `60` | `/chat` + `/chat/stream` (KB-5.15) |
| `CHAT_DB_PATH` / `MAX_CONVERSATIONS` | `./data/chat.db` / `200` | |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:3010,...` | CORS cho FE |
| `LOG_LEVEL` | `INFO` | logger `app.*` |

## Prompts

`SYSTEM_PROMPT_PATH` (mặc định `prompts/system_prompt.txt`). Thiếu file ⇒ **không** làm `/ready` đỏ: chat
dùng prompt fallback dựng sẵn trong code (KB-5.9).

## Running and Scripts

```bash
.venv/bin/python -m pytest -q                      # test
.venv/bin/python -m uvicorn app.main:app --port 8000
docker compose up -d --build                       # build + chạy (host 8010)
docker build -t kb-be:local .                      # chỉ build image
```

## Project Structure

```
Knowledge-base/
├── app/
│   ├── main.py                # routes + middleware + error handlers + lifespan
│   ├── core/                  # config, errors, auth, rate_limit, middleware, sse, embeddings,
│   │                          # provider_retry (cổng gọi provider), logging_setup
│   ├── services/              # document_service (index/retrieval/rerank), chat_service,
│   │                          # index_sync (hash+diff), rerank_cache, multi_query, dedup,
│   │                          # pii_service, conversation_store, startup_sync, health_service
│   └── models/schemas.py      # pydantic request/response
├── tests/                     # 320 test (pytest) + builders.py (BASE_SETTINGS 1 chỗ)
├── eval/                      # run_eval.py + qa_set.json (20 câu) + runs/*.json
├── prompts/system_prompt.txt
├── data/                      # chat.db (SQLite, KHÔNG commit)
├── Dockerfile · docker-compose.yml · .env.example
```

## Testing

```bash
$ .venv/bin/python -m pytest -q
320 passed, 1 warning in 1.15s
```

Nguyên tắc: **không** chạy lifespan, **không** load model/Chroma, **không** gọi mạng — service giả qua
`app.dependency_overrides` (`tests/conftest.py`), settings giả qua `tests/builders.BaseSettings`.

## Đo chất lượng RAG (eval harness)

```bash
# 1) (Tuỳ chọn) index lại trước khi đo
curl -X POST http://localhost:8010/documents/sync

# 2) Đo retrieval — KHÔNG gọi LLM, không tốn quota, tắt cache cho số thật
RERANK_CACHE_ENABLED=false .venv/bin/python eval/run_eval.py --mode retrieval --tag my-change

# 3) Đo câu trả lời thật qua Groq (/chat) — tốn 1 request/câu
.venv/bin/python eval/run_eval.py --mode full --tag my-change
```

Kết quả ghi vào `eval/runs/<timestamp>-<tag>-retrieval.json` (kèm **config đầy đủ** để tái lập).

| Run | Cấu hình | `hit@k` | `MRR` | `prec@k` | p50 |
|---|---|---|---|---|---|
| `kb54-before` | top-N 20, không multi-query | 1,0 | 0,975 | 0,533 | 9,70 s |
| `kb54-after` | top-N 20 + multi-query | 1,0 | 0,975 | 0,617 | 6,50 s |
| `kb54-control-topn4` | top-N 4, multi-query **off** (control) | 1,0 | **1,0** | 0,55 | **2,00 s** |
| **`kb58-top6-mq-fullpart`** (chốt) | top-N 6 + multi-query + chấm đủ dài | 1,0 | 0,975 | **0,617** | **3,44 s** |

Cách đọc: mọi thay đổi retrieval phải có cặp run trước/sau; khi nghi ngờ thì chạy **control run** — bài
học KB-5.4 ([ADR-0010](../docs/adr/0010-eval-la-cong-chat-luong.md)).

## Troubleshooting

| Triệu chứng | Nguyên nhân thường gặp | Xử lý |
|---|---|---|
| `/ready` = `degraded`, `collection is empty` | index chưa có / đã clear | `POST /documents/sync` (hoặc `refresh`) |
| `409 documents_folder_empty` | `DOCUMENTS_FOLDER` sai hoặc bị `.dockerignore` loại | kiểm `docker compose exec chatbot-api ls /app/Interview` |
| Container khởi động rất lâu lần đầu | tải model ~3,3 GB vào volume `hf-cache` | chờ lần đầu; các lần sau ~10 s |
| `sqlite3.OperationalError: unable to open database file` | volume `./data` chưa có / quyền ghi | `mkdir -p data && chmod u+w data` (app vẫn chạy, chỉ mất lịch sử) |
| `429 provider_rate_limited` | vượt TPM free tier (8.000 TPM) | chờ; giữ `PROVIDER_MAX_CONCURRENCY=1`; giảm `RETRIEVAL_K` |
| `429 rate_limited` | rate limit của mình (`RATE_LIMIT_*`) | chờ theo `Retry-After` hoặc tắt cờ |
| Câu trả lời chậm ~3–4 s mỗi câu **mới** | rerank CPU là chi phí thật | câu lặp đã có cache; muốn nhanh hơn: giảm `RERANK_TOP_N` (mất precision) |
| Đổi `CHUNK_SIZE`/`EMBEDDING_*` mà kết quả không đổi | `sync` chỉ so **nội dung file** | `DELETE /documents/clear` → `POST /documents/sync` |
| Rerank cache không hit sau restart | cache là **in-process** (TD-28) | bình thường; hit lại sau vài câu |

## License

MIT.

## Acknowledgements

- [LangChain](https://github.com/langchain-ai/langchain) · [ChromaDB](https://www.trychroma.com/) ·
  [sentence-transformers](https://www.sbert.net/) · [Groq](https://groq.com/) · [FastAPI](https://fastapi.tiangolo.com/)



