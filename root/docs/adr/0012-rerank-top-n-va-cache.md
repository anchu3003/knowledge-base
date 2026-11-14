# ADR-0012 — Cache rerank: LRU + TTL, khoá gồm `index_version` và tham số

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) · TD-28 mở (Skip) |
| **Ngày** | 2026-11-09 |
| **Liên quan** | KB-5.3, KB-5.8 (top-N 6), TD-15, TD-28, TD-29 · `architecture.md` §4 · code: `app/services/rerank_cache.py`, `document_service.py:579-600` |

## Context

Cross-encoder là phần **đắt nhất** của một câu hỏi: ~0,5 s/chunk × 6–20 chunk = 3–13 s tuỳ top-N
(ADR-0006). Khi ôn tập, user hỏi lại **đúng câu cũ** rất nhiều (đọc lại, so sánh, dạy lại) ⇒ chấm lại
từ đầu là lãng phí thuần tuý.

Nhưng cache trong RAG có cái bẫy chết người: **tài liệu đổi mà cache không biết** ⇒ trả kết quả của
phiên bản cũ.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **In-process LRU + TTL, khoá gồm `index_version`** (chọn) | 0 hạ tầng; tự vô hiệu khi index đổi; câu lặp 7,15 → 0,13 s | mất khi restart; không chia sẻ giữa worker | ⭐ 1 process, 1 user |
| Redis | chia sẻ, sống qua restart | thêm 1 container + serialize + key naming; phí cho 1 user | Nhiều worker/service |
| Cache trên đĩa (SQLite) | sống qua restart | thêm schema + dọn rác; lợi ích chỉ 1 lần/câu sau restart | Khi restart thường xuyên |
| Không cache | đơn giản, luôn đúng | câu lặp vẫn 3–4 s | Bộ eval (đo phải tắt cache) |

## Decision

`RerankCache` (OrderedDict + `threading.Lock`, LRU `RERANK_CACHE_MAX_ENTRIES=256`, TTL
`RERANK_CACHE_TTL_SECONDS=3600`), **khoá** = `sha256(index_version|k|top_n|config_fingerprint|query)`:

- **`index_version`** tăng mỗi khi index đổi (ingest/delete/clear/sync) ⇒ không cần hook xoá thủ công.
- **`k`, `top_n`, `config_fingerprint`** (hybrid, alpha, dedup, cap, model, threshold, candidate_k) ⇒ cùng
  câu hỏi nhưng khác tham số là entry khác.
- Query được **normalize** (strip + gộp whitespace + lowercase) ⇒ "Kafka  là gì?" dùng chung entry.
- Cache **tắt được** (`RERANK_CACHE_ENABLED=false`) — bắt buộc khi đo eval.

## Bằng chứng (số đo thật)

| Kịch bản | Không cache | Có cache | Run / nguồn |
|---|---|---|---|
| Câu lặp lại (cùng tham số) | **7,15 s** | **0,13 s** | KB-5.3 |
| p50 toàn bộ (20 câu, mỗi câu 1 lần) | 9,70 s (top-N 20) | 6,50 s (top-N 8) | `kb53-*` |
| Chốt cuối (top-N 6, mỗi part đủ dài) | — | **3,44 s** p50 | `kb58-top6-mq-fullpart` |

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Khoá chỉ băm query** (không có `index_version`): sửa tài liệu xong vẫn nhận câu trả lời dựa trên
  chunk **đã xoá** — user thấy trích dẫn không còn tồn tại. Đây là lý do tồn tại của `index_version`.
- **Khoá không có `top_n`/`config`**: đổi `RERANK_TOP_N` để thử nghiệm mà vẫn nhận kết quả cũ ⇒ kết luận
  sai khi đo (đã suýt xảy ra ở KB-5.8).
- **Bật cache khi chạy eval**: mọi lần đo thứ 2 trở đi đều "nhanh khủng khiếp" — phải tắt
  (`RERANK_CACHE_ENABLED=false`) đúng như `run_eval.py` làm.
- **TTL = vô hạn**: index không đổi nhưng ta muốn đo lại/thử model khác ⇒ entry cũ ám. TTL 1 h là van an
  toàn.

## Consequences

- **Được**: câu lặp gần như tức thì (0,13 s); key tự vô hiệu, không có hook rải rác.
- **Mất**: RAM (256 entry × ~ vài chục float — không đáng kể); cache mất khi restart (TD-28); câu **mới**
  vẫn 3,4 s — đây là giới hạn thật của CPU (TD-29 đã trả bằng top-N=6).
- **Tech debt**: **TD-28** (in-process, không chia sẻ) — **Skip** có lý do: đây là cache dẫn xuất, 1 người
  dùng, restart chỉ tốn lại ~3,4 s cho mỗi câu đã hỏi.

## Nếu làm lại thì khác gì

1. Thêm **metric hit rate** vào `/documents/status` (đã có `rerank_cache.stats()`, nhưng chưa ai xem) để
   biết TTL 1 h có phù hợp không.
2. Ghi **cache key version** (`v1`) vào khoá để đổi cấu trúc key không phải xoá tay.
3. Cân nhắc cache **retrieval** (kết quả hybrid) chứ không chỉ rerank — retrieval 0,18 s nên chưa cần,
   nhưng nếu corpus tăng 10× thì đây là bước tiếp theo.

## Revisit

Xem lại khi:

- Chạy **> 1 worker** hoặc restart thường xuyên (→ Redis/SQLite cache, TD-28).
- Câu **mới** cần < 2 s (hiện 3,4 s) ⇒ batch rerank / model nhỏ hơn / GPU.
- Tỉ lệ trùng câu hỏi < 10% trong log (cache không còn đáng giữ).
