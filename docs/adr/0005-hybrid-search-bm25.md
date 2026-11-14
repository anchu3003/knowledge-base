# ADR-0005 — Hybrid search: dense + BM25, gộp bằng alpha (không dùng 2 hệ tách rời)

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-08 |
| **Liên quan** | KB-2.2, KB-2.5, KB-5.1 (corpus reset) · `architecture.md` §4 · code: `app/services/document_service.py:404` (`_rebuild_bm25`), `:537` (alpha) · `HYBRID_ALPHA=0.5`, `HYBRID_CANDIDATE_K=20` |

## Context

Tài liệu kỹ thuật có 2 loại truy vấn khác nhau:

- **Ngữ nghĩa**: "khác nhau giữa JPA và Hibernate?" → dense embedding thắng.
- **Từ khoá hiếm**: `journal_mode=WAL`, `Mockito doThrow`, `Saga` → dense hay **trượt** vì token hiếm
  không kéo vector về đúng chunk; BM25 thắng.

Chạy dense thuần cho `hit@k 0,933` (15 câu, k=5) — nghĩa là ~7% câu **không có tài liệu đúng** trong top-k
dù đã có chunk đúng trong index.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Hybrid trong 1 truy vấn Chroma** (chọn) | Dense + `SparseVector` (BM25) gộp bằng trọng số; 1 round-trip; không phải merge kết quả thủ công | Phải tự build corpus BM25 trong RAM và **reset khi index đổi** (đã từng lệch — TD-13) | ⭐ Tài liệu kỹ thuật, 1 process |
| Dense thuần | Đơn giản nhất, p50 0,18 s | Trượt truy vấn từ khoá hiếm (`hit@k 0,933`) | Tài liệu văn xuôi thuần |
| BM25 thuần (`rank_bm25`) | Rất tốt cho từ khoá | Không hiểu ngữ nghĩa ("xe hơi" ≠ "ô tô") | Khi user toàn search mã lỗi |
| 2 hệ tách rời + RRF (reciprocal rank fusion) | Không cần Chroma hỗ trợ sparse | 2 lần truy vấn + tự chuẩn hoá thang điểm; code merge nhiều, dễ sai | Store không có sparse native |

## Decision

Bật hybrid (`ENABLE_BM25=true`) với **`HYBRID_ALPHA=0.5`** (dense/sparse cân bằng) và
`HYBRID_CANDIDATE_K=20` (gom 20 ứng viên trước khi rerank). Corpus BM25 giữ trong RAM
(`_corpus_texts`) và **rebuild** sau mọi thao tác đổi index (`_rebuild_bm25()` sau add/delete/sync — KB-5.1
sửa TD-13).

Lý do loại RRF: Chroma đã làm fusion trong 1 truy vấn; tự merge 2 danh sách chỉ thêm code sai số.

## Bằng chứng (số đo thật)

| Cấu hình | `hit@k` | `MRR` | `distinct_file_ratio` | p50 | Run |
|---|---|---|---|---|---|
| Dense thuần (k=5, không rerank) | 0,933 | 0,651 | 0,707 | 0,177 s | `2026-11-07T171534-baseline` |
| Hybrid + threshold 0,7 | **0,333** | 0,85 | 0,72 | 0,192 s | `kb22-thr07` |
| Hybrid, threshold tắt + dedup | **1,0** | 0,654 | 0,733 | 0,188 s | `kb22-dedup` |
| Hybrid, alpha 0,3 / 0,7 | (quanh 0,93–1,0) | ~0,65 | ~0,73 | ~0,19 s | `kb25-a03`/`kb25-a07` |

Bài học từ bảng: **hybrid + dedup** đưa `hit@k` từ 0,933 → 1,0; còn `SIMILARITY_THRESHOLD=0,7` **giết**
recall (0,333) vì score hybrid đã chuẩn hoá min-max — ngưỡng cosine không áp được cho score fusion ⇒
chốt `SIMILARITY_THRESHOLD=0` (`config.py:83-90`).

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Quên reset corpus BM25 sau re-index** (đúng TD-13): corpus cũ vẫn chứa chunk đã xoá ⇒ BM25 trả về
  chunk "ma", rerank chấm trên text không còn trong Chroma ⇒ nguồn trích dẫn không tồn tại.
- **Đặt `SIMILARITY_THRESHOLD` cho score hybrid**: đo được recall sụp 1,0 → 0,333; ngưỡng chỉ hợp cho
  **dense candidate** trước khi fusion (đó là lý do comment ở `config.py:86-89`).
- **Tăng alpha để "thiên dense"** khi thấy keyword trượt: alpha 0,7 không cải thiện trong grid đo; vấn đề
  thật là chunking/dedup, không phải trọng số.

## Consequences

- **Được**: keyword hiếm vẫn trúng; 1 truy vấn; p50 dense+hybrid ~0,18 s (rẻ so với rerank 3–4 s).
- **Mất**: RAM giữ toàn bộ text corpus (~601 chunk × 1.000 ký tự ≈ 0,6 MB — chấp nhận được); phụ thuộc
  `rank_bm25`; mọi thao tác index **phải** nhớ rebuild corpus (đã gom vào `_rebuild_bm25`).
- **Tech debt**: corpus build lại từ Chroma mỗi lần khởi động (đọc hết collection) ⇒ khởi động chậm thêm
  ~1 s ở 601 chunk (đo cùng startup sync 0,029 s khi không đổi file).

## Nếu làm lại thì khác gì

1. Viết **1 chỗ duy nhất** đổi index (một hàm `_mutate_index()`) bọc rebuild corpus + `index_version++`
   — hiện phải nhớ gọi ở 4 nơi, và TD-13 chính là do quên.
2. Đo **hybrid vs dense trên bộ câu hỏi nhiều keyword** (hiện bộ vàng 20 câu thiên ngữ nghĩa) để biết
   alpha thật sự có tác dụng khi nào.
3. Cân nhắc `bge-m3` (sparse native từ model) để bỏ `rank_bm25` + corpus RAM.

## Revisit

Xem lại khi:

- `hit@k` giảm dưới **0,95** trên bộ vàng mở rộng, hoặc thêm **≥ 10** câu hỏi dạng tra cứu từ khoá.
- RAM tiến trình **> 2 GB** (corpus lớn dần) hoặc startup > 5 s.
- ChromaDB đổi API sparse (đang là `chromadb.SparseVector`) khi nâng version.
