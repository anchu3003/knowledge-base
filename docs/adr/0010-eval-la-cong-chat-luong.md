# ADR-0010 — `eval/` là cổng chất lượng: đổi retrieval phải có số trước/sau

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-08 |
| **Liên quan** | KB-2.2, KB-2.5, KB-5.3, KB-5.4, KB-5.8, TD-29, TD-30 · `architecture.md` §4 · code: `eval/run_eval.py`, `eval/qa_set.json`, `eval/runs/*.json` |

## Context

Retrieval/RAG có rất nhiều "núm" (k, alpha, top-N, chunk size, dedup, multi-query). Sửa một núm theo cảm
giác rất dễ **tệ hơn** mà vẫn thấy "có vẻ tốt" — nhất là khi câu trả lời do LLM sinh ra luôn nghe hợp lý.
Đã xảy ra thật: KB-5.4 định chốt multi-query vì `precision@k 0,533 → 0,617`, nhưng **control run** cho
thấy chỉ cần hạ `RERANK_TOP_N` 20 → 4 là `MRR` đã 1,0 và p50 còn 2,0 s ⇒ công của multi-query chỉ là
phần phụ.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Bộ vàng cố định + script đo + lưu run JSON** (chọn) | so sánh được giữa các lần; số nằm trong repo; tái lập bằng 1 lệnh | bộ 20 câu nhỏ, thiên ngữ nghĩa; không đo "câu trả lời đúng" | ⭐ Đổi retrieval/rerank |
| Cảm nhận thủ công (hỏi vài câu) | nhanh | thiên lệch, không so được; đã từng suýt chốt sai | — |
| RAGAS/LLM-as-judge | đo được chất lượng câu trả lời | tốn quota, không ổn định, khó tái lập | Khi cần đo end-to-end quality |
| A/B trên user thật | đúng nhất | 1 user, không có traffic | Sản phẩm thật |

## Decision

1. Bộ vàng `eval/qa_set.json` (**20 câu** v3, mỗi câu có `expected_sources` + `keywords`).
2. `eval/run_eval.py` chạy **retrieval-only** (rẻ, không gọi LLM) và ghi
   `eval/runs/<timestamp>-<label>-retrieval.json` gồm **config đầy đủ** + `summary`.
3. **Quy tắc cổng**: mọi thay đổi ảnh hưởng retrieval phải kèm 1 cặp run `before`/`after` (cùng bộ câu) và
   chốt trên metric **còn dư địa**.
4. Khi nghi ngờ, chạy **control run**: thay đổi mình định làm vs thay đổi rẻ hơn (đổi tham số).

## Bảng: thay đổi nào đã chốt bằng số + ngưỡng dùng

| Thay đổi | Metric chốt | Trước → Sau | Run |
|---|---|---|---|
| Dedup + `MAX_CHUNKS_PER_FILE=2` (KB-2.2) | `hit@k` | 0,933 → **1,0** | `kb22-dedup` |
| Tắt `SIMILARITY_THRESHOLD=0,7` | `hit@k` | **0,333 → 1,0** | `kb22-thr07` vs `kb22-dedup` |
| Rerank bật (KB-2.5) | `MRR` | 0,654 → **1,0** (nhưng p50 0,19 → 9,7 s) | `kb25-final` |
| `RERANK_TOP_N` 20 → 8 (KB-5.3) | p50, giữ `MRR` | 9,70 → **6,50 s**, `MRR` 0,975 | `kb53-top8` |
| Cache rerank (KB-5.3) | câu lặp | **7,15 → 0,13 s** | `kb53-*` |
| `RERANK_TOP_N` 6 + per-part đủ dài (KB-5.8) | p50, giữ `MRR` | 6,50 → **3,44 s**, `MRR` 0,975, `prec@k` 0,617 | `kb58-top6-mq-fullpart` |
| Control: top-N 4 + multi-query off | `MRR`, p50 | `MRR 1,0`, p50 **2,00 s** ⇒ multi-query không phải đòn bẩy chính | `kb54-control-topn4` |

**Bài học ngưỡng (KB-5.4)**: đừng đặt ngưỡng "hit@k +5 điểm %" khi baseline đã 1,0 — không còn dư địa,
nên chốt theo metric còn dư địa (`precision@k`, p50) hoặc theo control run.

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Chốt theo 1 lần chạy**: p50 dao động theo tải máy (đo được 3,32 s vs 3,44 s cho cùng cấu hình). Cần
  nhìn cả `MRR`/`precision` chứ không chỉ latency.
- **Đo khi cache đang bật**: câu lặp được cache ⇒ latency đẹp giả tạo. `run_eval.py` tắt cache
  (`RERANK_CACHE_ENABLED=false`) khi đo.
- **Bộ câu hỏi chỉ 1 loại**: 20 câu hiện thiên ngữ nghĩa; câu hỏi dạng tra từ khoá chưa được đo ⇒
  hybrid/BM25 chưa có bằng chứng định lượng (xem ADR-0005 mục "Nếu làm lại").
- **Đổi nhiều núm cùng lúc**: không biết cái nào có tác dụng (đúng ca KB-5.4).

## Consequences

- **Được**: mọi thay đổi retrieval có số kèm theo; phát hiện được "cải tiến giả"; chi phí đo rẻ
  (retrieval-only, ~20–60 s cho 20 câu).
- **Mất**: bộ 20 câu do chính mình viết ⇒ thiên lệch theo tài liệu mình có; phải cập nhật khi thêm tài
  liệu mới. Chưa đo chất lượng câu trả lời (chỉ retrieval).
- **Tech debt**: TD-30 (multi-query heuristic chưa thử LLM-split) — **Skip** vì metric đã bão hoà.

## Nếu làm lại thì khác gì

1. Viết **bộ vàng trước** khi code retrieval (hiện viết sau, phải chỉnh lại expected_sources 2 lần).
2. Thêm **loại câu hỏi** vào `qa_set.json` (`semantic|keyword|comparison`) để đọc metric theo nhóm — hiện
   trộn hết, không biết hybrid giúp loại nào.
3. Lưu **cả p95** (hiện chỉ p50) — 1 user thì p95 mới là trải nghiệm "đôi khi rất chậm".

## Revisit

Xem lại khi:

- Bộ vàng **< 20 câu** hoặc tài liệu tăng **> 2×** (bộ câu hỏi phải phủ tài liệu mới).
- Cần đo **chất lượng câu trả lời** (không chỉ retrieval) ⇒ thêm LLM-as-judge chạy theo lô, chấp nhận tốn
  quota.
- `precision@k` < 0,5 trong **2 lần đo liên tiếp**.
