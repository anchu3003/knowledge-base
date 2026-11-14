# ADR-0003 — Embedding model: Qwen3-Embedding-0.6B chạy local CPU (float32)

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-08 (model) · 2026-11-10 (dtype fp32) |
| **Liên quan** | KB-6.2, KB-2.4, KB-5.14 (trả TD-14) · `architecture.md` §6 · code: `app/core/embeddings.py`, `app/core/config.py:26-33` |

## Context

Tài liệu là **tiếng Việt trộn tiếng Anh** (ghi chú Java/Spring, phỏng vấn, Kafka…). Hai lựa chọn lớn:

- Gọi API embedding (OpenAI/Gemini) ⇒ mỗi lần index lại là gửi **toàn bộ tài liệu** lên cloud, tốn tiền
  theo token, và mâu thuẫn với PII rule (ADR-0007).
- Chạy **local** ⇒ miễn phí, private, nhưng phải vừa CPU. Máy: i5-12600K (12 nhân), 32GB RAM, GPU
  GTX 1050 Ti 4GB (không đáng tin trong WSL) ⇒ ngân sách thực tế là **CPU + ~1 GB RAM cho model**.

Đo được trước khi chốt: index 56 file → **601 chunk**; embedding phải chạy lại toàn bộ khi đổi model/
dtype ⇒ thời gian re-index là chi phí thật, không phải cảm giác.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Qwen3-Embedding-0.6B** (chọn) | Đa ngữ tốt (VN+EN), 1024-d, 0.6B vừa CPU, chất lượng cao trong tầm 1B | Chậm hơn model nhỏ; 1024-d tốn RAM/disk hơn | ⭐ Local CPU, tài liệu đa ngữ |
| OpenAI `text-embedding-3-small` | Nhanh, rẻ, 1536-d, ổn định | Gửi **toàn bộ tài liệu** lên cloud; phụ thuộc mạng; đổi model = re-index + chi phí | Khi cần chất lượng cao và chấp nhận cloud |
| `bge-m3` | Đa ngữ mạnh, sparse+dense | Nặng hơn trên CPU (~2 GB, chậm hơn ~2×) | Khi cần sparse native từ model |
| `paraphrase-multilingual-MiniLM` | Rất nhẹ, nhanh | Chất lượng thấp với tài liệu kỹ thuật dài | Prototype, máy yếu |
| `sentence-transformers/all-mpnet-base-v2` | Nhẹ, phổ biến | **Yếu tiếng Việt** (chủ yếu EN) | Tài liệu thuần tiếng Anh |

## Decision

Dùng **`Qwen/Qwen3-Embedding-0.6B`**, chạy local CPU, `normalize_embeddings=True`, và **ép
`torch_dtype=float32`** (`EMBEDDING_TORCH_DTYPE`, mặc định `float32`).

Lý do loại phương án khác: API embedding vi phạm ràng buộc privacy + chi phí re-index; `bge-m3` nặng gấp
đôi cho lợi ích chưa đo; MiniLM/mpnet-base yếu tiếng Việt — tài liệu của tôi phần lớn là tiếng Việt.

## Bằng chứng (số đo thật)

| Chỉ số | bf16 (mặc định của model) | float32 (chốt) | Nguồn |
|---|---|---|---|
| Throughput embed | 1,87 chunk/s | **8,11 chunk/s** (64 chunk, máy rảnh) | microbench KB-5.14 |
| Re-index toàn bộ 601 chunk | **~22 phút** | **436,8 s = 7,3 phút** (local) · 537 s (container) | KB-5.14 verify |
| Dtype thực tế load | `torch.bfloat16` | `torch.float32` (kiểm `model.auto_model.dtype`) | KB-5.14 verify |

Vì sao bf16 chậm: CPU **không có kernel bf16** nhanh như GPU ⇒ PyTorch phải cast qua lại; đây là bẫy
im lặng (không lỗi, chỉ chậm 3–4×).

Chất lượng retrieval (bộ vàng 20 câu, `eval/runs/`): `hit@k 1,0` · `MRR 0,975` · `precision@k 0,617`
(2026-11-09T173719) — embedding **không** phải nút cổ chai sau khi có rerank (ADR-0006).

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Đổi dtype/model mà không re-index**: `float32` và `bfloat16` cho vector **khác nhau về số**; trộn 2
  loại trong cùng collection ⇒ cosine lệch nhẹ, retrieval tệ dần mà **không có lỗi nào bắn ra**. Đã phải
  clear + re-index toàn bộ khi đổi dtype ở KB-5.14.
- **Tin vào `torch_dtype` ở cấp ngoài `model_kwargs`**: LangChain chuyển tiếp `model_kwargs` cho
  `SentenceTransformer`; đặt sai cấp ⇒ `TypeError: unexpected keyword argument 'torch_dtype'` (đã gặp).
- **Benchmark bằng câu ngắn 1 dòng**: 64 chunk cùng nội dung cho số lạc quan; phải đo trên chunk thật
  (1.000 ký tự) mới thấy chi phí thật.

## Consequences

- **Được**: miễn phí, private, không quota; re-index 7,3 phút ⇒ dám thử nghiệm chunking/ model.
- **Mất**: ~600 MB RAM thường trú; embedding là phần chậm nhất của một lần sync (khi có file mới).
- **Tech debt**: chưa có `embedding_fingerprint` để **chặn** sync khi model/dtype khác (chỉ ghi comment);
  muốn đổi model phải nhớ clear collection.

## Nếu làm lại thì khác gì

1. Đo dtype **trước khi** index lần đầu (bf16 → fp32 là 3–4× cho miễn phí).
2. Ghi fingerprint (`model:dtype:dim`) vào metadata collection + chặn sync khi lệch — biến "phải nhớ"
   thành "máy chặn".
3. Benchmark trên **bộ chunk thật** ngay từ đầu, không dùng câu mẫu.

## Revisit

Xem lại khi **một** trong các điều kiện sau đúng:

- `hit@k` trên bộ vàng **< 0,90** hoặc bộ câu hỏi mở rộng lên ≥ 50 câu tiếng Việt chuyên ngành.
- Có GPU ≥ 8GB dùng được trong WSL (lúc đó bf16 + batch lớn có thể nhanh hơn 10×).
- Re-index toàn bộ **> 15 phút** lại (vd số chunk > 2.000) ⇒ cân nhắc model nhỏ hơn hoặc ONNX quantize.
