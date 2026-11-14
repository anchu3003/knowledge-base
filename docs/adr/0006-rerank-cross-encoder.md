# ADR-0006 — Rerank bằng cross-encoder local + dedup theo file

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-08 |
| **Liên quan** | KB-2.2 (dedup), KB-2.5 (rerank), KB-5.3, KB-5.8 · `architecture.md` §4 · code: `document_service.py:579` (top-N), `:404-423` (CrossEncoder), `app/services/dedup.py` · `RERANK_MODEL=BAAI/bge-reranker-v2-m3` |

## Context

Retrieval trả 20 ứng viên từ hybrid (ADR-0005) nhưng **thứ tự** vẫn sai: chunk đúng thường ở top-5..10,
và nhiều chunk đến từ **cùng 1 file** (tài liệu dài chiếm hết top-k) ⇒ câu trả lời thiếu nguồn khác.
Đo ban đầu: `MRR 0,654` (dense+hybrid) — nghĩa là câu trả lời đúng thường không nằm đầu danh sách.

Ràng buộc: chỉ có CPU; mỗi lần chấm cross-encoder là 1 forward pass **cho từng cặp (query, chunk)** ⇒
số ứng viên quyết định trực tiếp latency.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Cross-encoder `bge-reranker-v2-m3` local + dedup + top-N hẹp** (chọn) | `MRR 0,975–1,0`, `hit@k 1,0`; không tốn quota; chấm đúng "câu hỏi này với đoạn này" | CPU: ~0,4–0,6 s/chunk ⇒ phải giới hạn top-N + cache (ADR-0012) | ⭐ CPU, cần chất lượng cao |
| Không rerank | Nhanh (0,18 s) | `MRR` thấp, thứ tự sai ⇒ LLM trả lời lan man | Prototype |
| Rerank API (Cohere/Jina) | Nhanh, không tốn CPU | Tốn tiền/quota, gửi nội dung tài liệu ra ngoài | Khi đã có ngân sách |
| LLM-as-reranker | Chất lượng cao | 1 request/câu + chậm; quota Groq free | Khi cần "hiểu" câu hỏi phức tạp |

## Decision

1. **Dedup** trước rerank: gộp chunk gần trùng (`DEDUP_JACCARD_THRESHOLD=0,8`) và chặn
   `MAX_CHUNKS_PER_FILE=2` ⇒ đa dạng nguồn.
2. **Rerank** bằng `BAAI/bge-reranker-v2-m3` (CrossEncoder local), chỉ trên `RERANK_TOP_N=6` ứng viên.
3. **Điểm cuối** = rerank score (logits cross-encoder) — không trộn với score hybrid vì khác thang đo.

Lý do loại API rerank: gửi nội dung tài liệu (có thể chứa PII, xem ADR-0007) ra bên thứ ba, cộng thêm
chi phí — trong khi model local đủ tốt (`MRR 1,0` ở cấu hình cuối).

## Bằng chứng (số đo thật, bộ vàng 20 câu)

| Cấu hình | `hit@k` | `MRR` | `precision@k` | p50 | Run |
|---|---|---|---|---|---|
| Không rerank (dense+hybrid, 15 câu) | 0,933 | 0,651 | — | 0,18 s | `2026-11-07T171534` |
| Rerank top-N 20 | 1,0 | 0,975 | 0,617 | 9,70 s | `kb54-before` |
| Rerank top-N 8 | 1,0 | 0,975 | 0,617 | ~6,5 s | `kb53-top8` |
| **Rerank top-N 6** | 1,0 | 0,975 | 0,617 | **3,44 s** | `kb58-top6-mq-fullpart` |
| Rerank top-N 4 (control) | 1,0 | 1,0 | 0,55 | 2,00 s | `kb54-control-topn4` |

Dedup + cap 2/file: `distinct_file_ratio` 0,707 → **0,733–0,783** (`kb22-dedup`, `kb58-*`).

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Rerank toàn bộ 20 ứng viên cho mọi câu**: p50 9,7 s — gần gấp 3 lần top-6 mà chất lượng **không
  tăng** (`MRR` y hệt). Đây là chỗ dễ "tối ưu cảm giác" nhất.
- **Cộng score rerank với score hybrid**: hai thang đo khác nhau (logits vs cosine/min-max) ⇒ ứng viên
  hybrid thắng oan. Đã tránh bằng cách dùng rerank score làm điểm cuối.
- **Bỏ dedup**: 1 file dài chiếm 3–4 slot top-5 ⇒ câu trả lời chỉ dựa trên 1 tài liệu, dễ sai.
- **Chấm rerank trên chunk đã bị cắt cụt** (bản đầu cắt 500 ký tự): mất nửa bằng chứng ⇒ rerank chấm
  sai. KB-5.8 sửa thành chấm **đủ độ dài** từng chunk của multi-query part.

## Consequences

- **Được**: `MRR 0,975` / `hit@k 1,0` — nguồn đúng luôn trong top-3 trả về; đa dạng nguồn.
- **Mất**: 3,44 s/câu trên CPU (chiếm ~90% latency retrieval); ~600 MB RAM thêm cho CrossEncoder.
  Câu **mới** vẫn 3,4 s; chỉ câu lặp mới nhanh nhờ cache (ADR-0012).
- **Tech debt**: TD-28 (cache in-process) — Skip; TD-29 đã trả bằng top-N=6.

## Nếu làm lại thì khác gì

1. Chốt top-N bằng **control run** ngay từ đầu (bài học KB-5.4: thay đổi "cải tiến" có thể chỉ là do
   tham số khác) — xem ADR-0010.
2. Chấm rerank **song song** nhiều cặp (batch) thay vì tuần tự nếu `torch` cho phép batch hiệu quả trên
   CPU — chưa đo, để dành khi cần < 2 s.
3. Lưu ý ngay từ đầu: rerank score ≠ score hiển thị cho user; UI chỉ nên hiện "nguồn", không hiện điểm.

## Revisit

Xem lại khi:

- p95 latency > **6 s** hoặc cần < 2 s cho câu mới ⇒ thử batch rerank / model nhỏ hơn
  (`bge-reranker-base`) / ONNX.
- `precision@k` < 0,55 hoặc câu trả lời thiếu ý dù `hit@k = 1,0`.
- Có GPU dùng được (rerank là phần hưởng lợi nhiều nhất từ GPU).
