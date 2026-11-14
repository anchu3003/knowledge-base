# Phase 2 — RAG quality (Done 2026-11-07)

> Mục tiêu phase: sửa "5 tài liệu giống nhau", tăng độ chính xác/grounding, trích dẫn nguồn rõ ràng —
> **làm bằng số đo**, không bằng cảm tính. Nguyên tắc: *đo trước → sửa → đo lại*, mỗi ticket so với baseline.

## Đã có gì sau phase

| Ticket | Kết quả |
|---|---|
| KB-2.1 | **Eval harness** (`Knowledge-base/eval/`): 15 câu vàng + `run_eval.py` (`--mode retrieval\|full`, `--rerank`, `--k`, `--sleep`, `--build-index`); metric `hit@k`, `MRR`, `dup_ratio`, `precision@k`, `distinct_file_ratio`, `citation_presence`, `inline_citation_presence`, `latency_p50`; snapshot JSON ở `eval/runs/` |
| KB-2.2 | `app/services/dedup.py` + hậu xử lý retrieval: dedup Jaccard 0.8 + **cap 2 chunk/file**; `SIMILARITY_THRESHOLD` **có tác dụng** (lọc dense, default 0); chunk ID ổn định `sha1(source\|chunk_index\|text)[:16]` + `upsert`; trả `chunk_id`; **trả TD-13** (reset BM25 corpus) |
| KB-2.3 | Citation **inline** `[S1]` ↔ `sources[{citation_id, chunk_id, snippet}]`; `build_context` có budget `CONTEXT_MAX_CHARS=6000` (bỏ cắt 500 ký tự); prompt file + fallback đồng bộ rule cite + "không có trong knowledge base" |
| KB-2.4 | Chunking `.md` **2 tầng** (heading H1–H3 → size) + `heading_path`; re-index thật **56 file → 601 chunk**; dọn corpus còn `Backend&Devops`; `qa_set` v2; **trả TD-7** |
| KB-2.5 | Tune bằng grid 10 cấu hình: `RETRIEVAL_K 5 → 3`, giữ `HYBRID_ALPHA=0.5`, `MAX_CHUNKS_PER_FILE=2`, `ENABLE_RERANK=true`, `SIMILARITY_THRESHOLD=0.0`; **trả TD-8**; thêm TD-15 |

## Cách chạy ở thời điểm này

```bash
cd Knowledge-base

# Test
.venv/bin/python -m pytest -q                     # 46 passed

# Đo retrieval (không tốn quota LLM)
SIMILARITY_THRESHOLD=0 .venv/bin/python eval/run_eval.py --mode retrieval --tag check

# Đo câu trả lời thật (Groq free tier: TPM 8000 ⇒ PHẢI nghỉ giữa các câu)
.venv/bin/python eval/run_eval.py --mode full --sleep 25 --tag check

# Re-index (⚠️ ~22 phút trên CPU, TD-14)
.venv/bin/python eval/run_eval.py --mode retrieval --build-index --limit 1
```

Chạy app: `uvicorn app.main:app` (index 601 chunk có sẵn trong `chroma_db/`, gitignored).

## Số đo chốt (2026-11-07, corpus 56 file / 601 chunk, 15 câu)

| Metric | Trước phase (KB-2.1 baseline) | Sau phase (KB-2.5) |
|---|---|---|
| `hit@k` | 0.933 (k=5) | **1.0** (k=3) |
| `MRR` | 0.651 | **1.0** |
| `precision@k` | 0.347 | **0.533** |
| `distinct_file_ratio` | 0.707 | 0.756 |
| `citation_presence` | 0.0 | **0.933** |
| `inline_citation_presence` | 0 | **0.800** |
| `latency_p50` (retrieval) | 0.177s (rerank off) | 8.16s (rerank on — TD-15) |

## Cái gì CHƯA có (đừng tưởng đã có)

- **Chưa có CI/CD** — test/verify vẫn chạy tay.
- **Rate limit/backoff thật** cho Groq: chỉ có `--sleep` trong harness; API `/chat` chưa retry (`429` → lỗi) → Phase 3.
- **Error handling BE** chưa chuẩn hoá (map lỗi provider → HTTP) → Phase 3.
- **SSE (`/chat/stream`) chưa kiểm** sau khi đổi `build_context`/`sources` (mới test qua `/chat`).
- **FE chưa dùng** field mới (`citation_id`, `heading_path`, `snippet`) — FE vẫn dedup sources theo `file_path` (**TD-12**, Phase 4).
- `inline_citation_presence` mới 0.800 (3/15 câu chỉ ghi ở dòng `Nguồn:`).
- **TD-1** (regex PII, chưa NER), **TD-2** (conversation in-memory), **TD-14** (embedding bfloat16 CPU), **TD-15** (rerank ~8s) vẫn mở.
- Corpus chỉ còn `Backend&Devops` (user dọn tay) ⇒ các chủ đề English/Frontend không còn để hỏi.

## Bài học của phase

1. **Metric phải khớp triệu chứng người dùng cảm nhận.** `dup_ratio` (Jaccard ≥ 0.8) = 0 ở mọi cấu hình, tưởng "không có lỗi"; `distinct_file_ratio` mới lộ ra 5/5 hit cùng 1 file. Đổi metric xong mới sửa đúng (cap/file là thứ cứu, không phải dedup).
2. **Metric ở sàn/sát trần thì vô dụng.** `hit@k` chạm 1.0 rất sớm ⇒ phải có `MRR`, `precision@k` để còn dư địa đo tiến bộ (chọn k=3 thay vì k=5 nhờ precision).
3. **Luôn có run đối chứng.** Bật/tắt tính năng mới và tái lập đúng baseline cũ là cách rẻ nhất chứng minh refactor không phá gì (bắt được cả bug BM25 corpus — TD-13). Lần chạy grid quên `--rerank off` cũng cho bài học: kết quả chỉ đáng tin khi biết rõ mình đang bật cái gì.
4. **"Có citation" ≠ "citation inline".** Model chọn đường rẻ nhất (dồn nhãn xuống cuối) ⇒ phải định nghĩa metric riêng (`inline_citation_presence`) và siết prompt, không tin cảm giác "đã có trích dẫn".
5. **Đo trước khi tối ưu, và tối ưu cái đang chạy thật.** Rerank chưa từng bật nên mọi so sánh trước đó đều thiếu; bật rerank đưa `MRR` lên 1.0 — nhưng phải trả giá 8s/query (TD-15).
6. **Chọn theo loại lỗi không muốn, không chỉ theo điểm.** cap=3 cho precision cao hơn nhưng tái hiện "1 file chiếm slot" ⇒ giữ cap=2.
