# ADR-0002 — Vector store: ChromaDB persistent chạy local

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-08 |
| **Liên quan** | KB-2.1 → KB-2.5, KB-5.1 · `architecture.md` §4 · code: `app/services/document_service.py:63` |

## Context

Knowledge base cá nhân, **1 người dùng**, ~56 file Markdown/PDF/DOCX → **601 chunk**. Máy chạy WSL2
(i5-12600K / 32GB RAM, không có GPU dùng được) và mọi thứ chạy bằng `docker compose` trên **một** máy.
Ràng buộc:

- Cần **hybrid search** (dense + BM25) chứ không chỉ cosine — tài liệu kỹ thuật có nhiều từ khoá hiếm
  (`Saga`, `Mockito`, `journal_mode=WAL`) mà embedding thuần hay bỏ sót.
- Cần **xoá theo file** khi tài liệu bị xoá (sync tăng dần ở ADR-0011) → phải lọc/xoá theo metadata
  `source`, không chỉ theo id.
- Không muốn thêm hạ tầng phải vận hành (AGENTS.md §3.4). Không có nhu cầu multi-tenant, replication.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **ChromaDB `PersistentClient`** (chọn) | Nhúng trong process, 0 container thêm; có **sparse vector** native (BM25/hybrid 1 truy vấn); `where` filter theo metadata; persist = 1 thư mục | Single-writer (SQLite làm backend); ít option tuning ANN; API còn đổi giữa các minor | ⭐ 1 process, < 100k chunk, cần hybrid |
| Qdrant (server) | ANN mạnh, filter tốt, multi-client | Thêm 1 container + network hop + phải backup riêng; sparse cần cấu hình thêm | Nhiều service cùng dùng, > 1M vector |
| pgvector (Postgres) | Có transaction/SQL quen thuộc, 1 DB cho mọi thứ | Cần Postgres; hybrid phải tự ghép BM25 (tsvector) + dense; nặng cho 1 user | Đã có Postgres, cần join dữ liệu quan hệ |
| FAISS (thư viện) | Nhanh nhất, kiểm soát index | **Không** có metadata/filter/persist sẵn → phải tự viết store id→metadata, tự map khi xoá file | Batch offline, không cần update |

## Decision

Chọn **ChromaDB `PersistentClient`** với `path=CHROMA_DB_PATH` (`./chroma_db`), telemetry tắt:

- Dense dùng `HuggingFaceEmbeddings` (ADR-0003); sparse dùng `chromadb.SparseVector` cho BM25 —
  hybrid chạy **trong 1 truy vấn**, không phải merge 2 hệ.
- Metadata mỗi chunk có `source`, `file_hash`, `heading_path`, `chunk_id` → xoá/cập nhật theo file dễ.
- Lý do loại: Qdrant/pgvector thêm 1 hệ phải vận hành mà lợi ích (ANN tuning, multi-client) không dùng
  tới; FAISS thiếu metadata store ⇒ đúng chỗ dễ sinh bug nhất (xoá file không sạch index).

## Bằng chứng (số đo thật)

| Chỉ số | Số | Nguồn |
|---|---|---|
| Chunk trong collection | **601** (56 file) | `eval/runs/2026-11-09T173719-…json` → `collection_count: 601` |
| Retrieval p50 (dense + hybrid, chưa rerank) | **0,177 s** (15 câu) | `2026-11-07T171534-baseline-retrieval.json` |
| Hybrid alpha / candidate pool | `0.5` / `20` ứng viên | `config.py:110-111` |
| Xoá theo file khi sync | xoá theo `where={"source": path}` | `document_service.py:719` (`sync_documents`) |

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **FAISS + tự quản metadata**: xoá 1 file phải xoá đúng N chunk theo id; lệch id ⇒ chunk "mồ côi" vẫn
  được retrieve và trả về nội dung đã xoá. Đây đúng là lớp bug mà `index_sync.diff_indexed` phải chống.
- **Đặt Chroma ở chế độ `HttpClient` cho 1 process**: thêm 1 container, mà vẫn single-writer ⇒ chỉ thêm
  điểm chết.
- **Đổi embedding model nhưng dùng lại collection**: vector 1024-d của model khác **không cùng không
  gian**; Chroma không báo lỗi nếu dimension tình cờ bằng nhau ⇒ retrieval tệ dần mà không ai biết
  (xem ADR-0003, mục "Nếu làm lại").

## Consequences

- **Được**: 0 hạ tầng thêm; hybrid 1 truy vấn; backup = `cp -r chroma_db`; test tích hợp chạy được
  trong process (không cần mock server).
- **Mất**: không chạy được **nhiều writer** (2 container cùng mount `chroma_db` là hỏng — đã gặp khi
  verify KB-5.14: app local và container cùng mở index); không có ANN tuning cho > 100k chunk.
- **Tech debt liên quan**: TD-7 (đã trả), TD-13 (BM25 corpus lệch sau re-index — đã trả ở KB-5.1).

## Nếu làm lại thì khác gì

1. Đặt `hnsw:space=cosine` **tường minh** trong `create_collection` (hiện dựa vào mặc định + tự
   normalize vector) để người sau đọc là biết, không phải suy từ `embeddings.py`.
2. Ghi **`embedding_fingerprint`** (`model:dtype:dim`) vào metadata collection ngay từ đầu và **chặn
   sync** nếu khác — thay cho việc phải nhớ "đổi dtype/model thì clear + re-index" (hiện chỉ ghi comment
   ở `config.py:28-33` và `.env.example`).
3. Tách class `VectorStore` khỏi `DocumentService` (hiện 700+ dòng làm 6 việc) để đổi store về sau
   không phải sửa toàn bộ service.

## Revisit

Xem lại khi **một** trong các điều kiện sau đúng:

- Số chunk **> 100.000** hoặc retrieval p95 > 500 ms (đo bằng `eval/run_eval.py`).
- Cần **> 1 process** cùng ghi index (vd chạy 2 worker uvicorn — xem TD-17).
- Cần filter/lọc phức tạp (theo tag, tenant, thời gian) hoặc replication.
