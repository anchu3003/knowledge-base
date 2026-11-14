# Phase 6 — Tech refresh

| | |
|---|---|
| **Trạng thái** | ✅ Done |
| **Ticket** | KB-6.1 → KB-6.4 |
| **Ngày** | 2026-11-07 |

## Phase này làm gì

Đồng bộ tech stack: pin dependency, nâng runtime Python, và chuyển embedding/reranker sang **đa ngữ**
(phục vụ tài liệu tiếng Việt).

- **KB-6.1** — range-pin deps + Dockerfile Python 3.11 → **3.13** (base chạy 3.13.18).
- **KB-6.2** — embedding **`Qwen/Qwen3-Embedding-0.6B`** (env `EMBEDDING_MODEL`, 1024-dim, đa ngữ).
- **KB-6.3** — reranker **`BAAI/bge-reranker-v2-m3`** (env `RERANK_MODEL`, đa ngữ).
- **KB-6.4** — FE pin dep `latest` → version cụ thể; dọn key `eslint` khỏi `next.config.mjs`.

## Cách chạy ở thời điểm này

- BE: Python **3.13** (Docker) / 3.12 (local). `docker compose up`.
- **Đổi embedding model ⇒ PHẢI re-index**: xoá `chroma_db/` hoặc `POST /documents/refresh`.
- FE: `npm run build` / `npm run dev` (Node LTS 26).

## Cái gì chưa có (phải chạy thật mới xác nhận)

- **TD-6**: full Docker image build (`python:3.13` + torch) chưa chạy ở máy dev.
- **TD-7**: re-index với Qwen3-Embedding chưa chạy → chưa xác nhận retrieval tiếng Việt.
- **TD-8**: reranker `bge-reranker-v2-m3` chưa load/đo thật.

## Bài học

- Tách config ra env **từ sớm** ⇒ đổi embedding/reranker chỉ cần đổi 1 biến (KB-6.3 gần như zero-code).
- `Qwen3-Embedding` & `bge-reranker-v2-m3` đều **ST-compatible**, không cần `trust_remote_code`.
- Đổi **embedding dimension** (768→1024) ⇒ buộc re-index (collection cũ lỗi dimension nếu không xoá).
- Pin `latest` → version đang cài là cách "an toàn" để reproducible mà không rủi ro nâng cấp.
