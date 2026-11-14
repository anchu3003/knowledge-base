# ADR index — lộ trình đọc & câu hỏi ôn tập

> 17 quyết định lớn của dự án, viết lại **vì sao** (không phải "hiện tại là gì" — cái đó ở
> [`../../architecture.md`](../../architecture.md)). Mỗi ADR có: Context → Options → Decision →
> **Bằng chứng (số đo thật)** → Anti-pattern → Consequences → **Nếu làm lại thì khác gì** → Revisit.
>
> **Khi thêm ADR mới**: đánh số tiếp, thêm 1 dòng vào bảng dưới, cập nhật lộ trình đọc nếu cần.

## Bảng tra nhanh

| Số | Quyết định | Nhóm | Trạng thái | Ticket | Ngày |
|---|---|---|---|---|---|
| [0001](0001-llm-provider-groq.md) | LLM provider: Groq free tier | Runtime | Accepted | KB-0.2, KB-0.4 | 2026-11-07 |
| [0002](0002-vector-store-chromadb.md) | Vector store: ChromaDB persistent local | Retrieval | Accepted | KB-2.1–2.5 | 2026-11-08 |
| [0003](0003-embedding-model-qwen3.md) | Embedding: Qwen3-Embedding-0.6B local CPU, **float32** | Retrieval | Accepted | KB-6.2, KB-5.14 | 2026-11-08 / 11-10 |
| [0004](0004-chunking-markdown-heading.md) | Chunking theo heading + `heading_path` | Retrieval | Accepted | KB-2.x | 2026-11-08 |
| [0005](0005-hybrid-search-bm25.md) | Hybrid dense + BM25, `HYBRID_ALPHA=0.5` | Retrieval | Accepted | KB-2.2, KB-2.5 | 2026-11-08 |
| [0006](0006-rerank-cross-encoder.md) | Rerank cross-encoder local + dedup theo file | Retrieval | Accepted | KB-2.2, KB-2.5, KB-5.8 | 2026-11-08 |
| [0007](0007-pii-redaction-o-cong-ra.md) | PII redaction ở **cổng ra**, mặc định BẬT | Runtime / an toàn | Accepted (TD-1 đóng) | KB-1.1–1.3 | 2026-11-07 |
| [0008](0008-error-taxonomy-va-retry.md) | `AppError` + 1 cổng provider (semaphore + retry) | Runtime / an toàn | Accepted (TD-17 mở) | KB-3.1, KB-3.2 | 2026-11-08 |
| [0009](0009-sse-streaming-contract.md) | Hợp đồng SSE `start → token* → (end or error)` | Runtime | Accepted | KB-3.3, KB-3.4 | 2026-11-08 |
| [0010](0010-eval-la-cong-chat-luong.md) | `eval/` là cổng chất lượng (số trước/sau) | Dữ liệu / vận hành | Accepted | KB-2.2–2.5, KB-5.8 | 2026-11-08 |
| [0011](0011-index-tang-dan-theo-hash.md) | Index tăng dần theo hash nội dung | Dữ liệu / vận hành | Accepted | KB-5.1 | 2026-11-09 |
| [0012](0012-rerank-top-n-va-cache.md) | `RERANK_TOP_N=6` + cache LRU/TTL theo `index_version` | Dữ liệu / vận hành | Accepted (TD-28 Skip) | KB-5.3, KB-5.8 | 2026-11-09 |
| [0013](0013-multi-query-heuristic.md) | Multi-query bằng heuristic (không LLM) | Dữ liệu / vận hành | Accepted (TD-30 Skip) | KB-5.4, KB-5.8 | 2026-11-09 |
| [0014](0014-lich-su-chat-sqlite.md) | Lịch sử chat: SQLite WAL, redact trước khi lưu | Dữ liệu / vận hành | Accepted | KB-5.2 | 2026-11-09 |
| [0015](0015-fe-state-khong-dung-thu-vien.md) | FE state: store ngoài React, không Zustand/Redux | Frontend | Accepted | KB-4.9, KB-5.2 | 2026-11-09 |
| [0016](0016-render-streaming-plain-text.md) | Stream plain text, markdown parse 1 lần | Frontend | Accepted (TD-21/22 trả) | KB-5.6 | 2026-11-09 |
| [0017](0017-moi-truong-dev-wsl2-va-docker.md) | Dev env: WSL2 + `uv`/`fnm` + docker native | Dev env | Accepted (TD-24 Skip) | KB-7.1, KB-5.10 | 2026-11-09 |

## 3 lộ trình đọc

| Lộ trình | Thứ tự | Vì sao thứ tự này |
|---|---|---|
| **Người mới** (~30 phút) | 0001 → 0003 → 0004 → 0009 | Đi theo **một câu hỏi của user**: model nào trả lời (0001) → tài liệu thành vector thế nào (0003, 0004) → câu trả lời về UI ra sao (0009). Chưa cần rerank/eval. |
| **Ôn phỏng vấn backend** | 0002 → 0005 → 0006 → 0012 → 0013 | Đi theo **chuỗi quyết định có đánh đổi**: chọn store (0002) → hybrid (0005) → rerank (0006) → tối ưu latency (0012) → khi nào thêm phức tạp là vô ích (0013). Đây là 5 câu dễ bị hỏi "sao không dùng X". |
| **Vận hành / deploy** | 0011 → 0014 → 0017 (+ TD-24/25) | Đi theo **vòng đời dữ liệu & môi trường**: index cập nhật thế nào (0011) → lịch sử lưu ở đâu (0014) → máy/container chạy ra sao (0017). Đọc kèm §7 `Backlog.md` để biết cái gì **chưa** làm. |

Ngoài ra: đọc [0007](0007-pii-redaction-o-cong-ra.md) + [0008](0008-error-taxonomy-va-retry.md)
**trước khi sửa bất kỳ endpoint nào** — chúng là luật chung (PII + envelope lỗi).

## Câu hỏi ôn tập (28 câu, nhóm theo chủ đề)

### A. Retrieval (ADR-0002 → 0006, 0010)

1. **Vì sao chọn ChromaDB thay vì Qdrant/pgvector cho 601 chunk?** → Nhúng trong process, 0 container
   thêm, sparse native cho hybrid; Qdrant/pgvector chỉ đáng khi nhiều service/multi-client. *(0002)*
2. **Vì sao FAISS bị loại dù nhanh nhất?** → Không có metadata store/filter/persist ⇒ phải tự quản
   id→metadata — đúng chỗ sinh bug "chunk mồ côi" khi xoá file. *(0002)*
3. **bf16 vs float32 trên CPU khác nhau bao nhiêu, vì sao?** → 1,87 vs 8,11 chunk/s (nhanh ~3–4×): CPU
   không có kernel bf16 nên PyTorch phải cast; 601 chunk: 22 phút → 7,3 phút. *(0003)*
4. **Đổi embedding model/dtype mà không re-index thì sao?** → Vector khác không gian, cosine lệch,
   retrieval tệ dần mà **không có lỗi nào** — phải clear + sync lại. *(0003)*
5. **Vì sao chunk theo heading rồi vẫn phải cắt theo size?** → `MarkdownHeaderTextSplitter` không giới hạn
   độ dài; section 8.000 ký tự sẽ ăn hết context khi rerank. *(0004)*
6. **`SIMILARITY_THRESHOLD=0,7` gây ra chuyện gì?** → `hit@k` sụp 1,0 → 0,333 vì score hybrid đã min-max
   normalize; ngưỡng cosine không áp được ⇒ chốt 0. *(0005)*
7. **Hybrid giúp loại câu hỏi nào?** → Từ khoá hiếm (`journal_mode=WAL`, `Mockito doThrow`); đo tổng
   `hit@k` 0,933 → 1,0. *(0005)*
8. **Vì sao rerank top-N 20 chậm gấp 3 mà chất lượng như top-N 6?** → Cross-encoder chấm từng cặp trên
   CPU: 20 cặp ≈ 9,7 s vs 3,44 s, `MRR` y hệt 0,975. *(0006, 0012)*
9. **Dedup/cap chunk theo file để làm gì?** → Tránh 1 tài liệu dài chiếm hết top-k;
   `distinct_file_ratio` 0,707 → 0,78. *(0006)*
10. **Vì sao phải có control run khi đánh giá một cải tiến?** → KB-5.4: multi-query "9,7 → 6,5 s" nhưng
    control (top-N 4) cho `MRR 1,0` + 2,0 s ⇒ đòn bẩy là top-N. *(0010, 0013)*
11. **Ngưỡng chốt metric nên đặt trên metric nào?** → Metric còn dư địa: `hit@k` đã 1,0 thì đừng đặt
    "+5 điểm %", chốt theo `precision@k`/p50. *(0010)*

### B. Runtime & an toàn (ADR-0001, 0007 → 0009)

12. **Vì sao redact ở cổng ra chứ không phải lúc ingest?** → Ingest redaction làm lệch retrieval (câu hỏi
    có email thật không khớp chunk đã che — KB-1.2); cổng ra chặn đúng chỗ rò. *(0007)*
13. **Vì sao `PROVIDER_MAX_CONCURRENCY=1`?** → TPM free tier: 2 câu song song ~1.500 token/câu dễ vượt
    trần ⇒ 429 dù chỉ hỏi 2 câu. *(0008)*
14. **Retry đặt ở đâu, vì sao không retry mọi tầng?** → 1 cổng `ProviderThrottle` (semaphore + retry 2 +
    jitter, đọc `Retry-After`); 2 tầng retry = nhân số lần gọi, đốt quota. *(0008)*
15. **Response lỗi có schema gì, `request_id` từ đâu?** → `{"error":{code,message,request_id}}`;
    `RequestIDMiddleware` (lớp ngoài) gắn ⇒ 401/429/500 đều có. *(0008, 0009)*
16. **SSE heartbeat giải quyết gì?** → Idle timeout của proxy: quá 15 s không event thì gửi `: ping` để
    giữ kết nối (rerank 3–4 s). *(0009)*
17. **User F5 giữa lúc stream thì phần đã sinh xử lý thế nào?** → Generator bị cancel, service lưu
    **partial answer** (đã redact) vào SQLite. *(0009, 0014)*
18. **Vì sao middleware phải pure ASGI?** → `BaseHTTPMiddleware` buffer body ⇒ mất streaming; RequestID/
    Auth/RateLimit đều pure ASGI. *(0009)*

### C. Vận hành & dữ liệu (ADR-0010 → 0014)

19. **Sync khác Refresh ở đâu?** → Sync diff theo `sha256(nội dung)[:16]`, chỉ embed file đổi (~1,2 s/file),
    chat vẫn trả lời trong lúc sync; Refresh clear toàn bộ (22 phút → 7,3 phút với fp32) và mất index tạm
    thời. *(0011)*
20. **Guard "folder rỗng" để làm gì?** → Không có guard, sync hiểu "mọi file bị xoá" ⇒ xoá sạch 601 chunk
    (đã xảy ra ở KB-4.10); guard trả 409 `documents_folder_empty`. *(0011)*
21. **Cache rerank phải có gì trong khoá, vì sao?** → `index_version` (index đổi ⇒ vô hiệu) +
    `k`/`top_n`/config + query normalize; thiếu `index_version` ⇒ trả lời dựa trên tài liệu đã xoá.
    *(0012)*
22. **Vì sao tắt cache khi chạy eval?** → Câu lặp được cache làm latency đẹp giả tạo (0,13 s vs 7,15 s)
    ⇒ kết luận sai. *(0012)*
23. **Multi-query tách câu thế nào, cải thiện metric nào?** → Regex `so với|and|vs|;|đồng thời|và` (bảo vệ
    code trong backtick); chỉ tăng `precision@k` 0,533 → 0,617, không tăng `hit@k`/`MRR`. *(0013)*
24. **Lịch sử chat lưu ở đâu, redact lúc nào, giới hạn gì?** → SQLite stdlib + WAL `./data/chat.db`,
    redact **trước khi lưu**, `MAX_CONVERSATIONS=200`, DB lỗi ⇒ app vẫn chạy in-memory. *(0014)*

### D. Frontend & môi trường (ADR-0015 → 0017)

25. **Vì sao không dùng Zustand/Redux?** → 1 loại state, 0 dependency: store ngoài React +
    `useSyncExternalStore` + `getServerSnapshot` rỗng (không hydration mismatch); server là nguồn sự thật.
    *(0015)*
26. **Vì sao stream plain text thay vì markdown realtime?** → Markdown mỗi token = 300 lần parse/câu
    (O(n²)) + message cũ re-render 40 lần; nay 0 khi stream, 1 khi `end` — cái giá: text chưa format.
    *(0016)*
27. **Vì sao code phải ở Linux FS + docker engine native?** → `/mnt/d` chậm, watcher không ổn định;
    Desktop integration hay hỏng; native cho `docker info` trỏ `/var/lib/docker`. *(0017)*
28. **Image BE từng 16,5 GB vì đâu, sửa thế nào còn 2,68 GB?** → torch kéo ~3 GB gói `nvidia-*` + `/wheels`
    sót layer; sửa: torch CPU-only + `RUN --mount=type=bind` thay `COPY` (layer COPY không xoá được bằng
    `RUN rm`). *(0017)*

## Liên quan

- [`../../architecture.md`](../../architecture.md) — hiện trạng kiến trúc (ADR trả lời "vì sao").
- [`../../Backlog.md`](../../Backlog.md) — ticket + §7 tech debt (những gì **chưa** làm).
- [`../phases/`](../phases/) — nhật ký từng phase.

