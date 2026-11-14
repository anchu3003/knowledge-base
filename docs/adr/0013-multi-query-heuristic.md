# ADR-0013 — Multi-query bằng heuristic (regex), không dùng LLM/LangGraph

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) · TD-30 mở (Skip) |
| **Ngày** | 2026-11-09 |
| **Liên quan** | KB-5.4, KB-5.8, TD-30, TD-29 · `architecture.md` §4 · code: `app/services/multi_query.py`, `document_service.py:447` (`_initial_retrieval`) · `MULTI_QUERY_ENABLED=true`, `MULTI_QUERY_MAX_PARTS=3` |

## Context

Câu hỏi ôn tập hay có **nhiều ý trong 1 câu**: *"So sánh JPA và Hibernate, khi nào dùng cái nào?"*.
Retrieve 1 lần với cả câu ⇒ embedding bị "pha loãng", top-k chỉ phủ một nửa ý, câu trả lời thiếu phần
sau. Epic Phase 5 ghi "LangGraph (multi-step)" — tức phương án ban đầu là **LLM tách câu + nhiều vòng
retrieve**.

Ràng buộc: mỗi request LLM tốn quota Groq free tier; latency đã 3–4 s cho rerank (ADR-0006).

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Heuristic: tách theo dấu hiệu ngôn ngữ** (chọn) | 0 ms, 0 quota; kết quả đo được (precision 0,533 → 0,617) | không hiểu ngữ nghĩa; bỏ sót câu phức tạp | ⭐ Câu hỏi có "và/so với/khi nào/dấu ;" |
| LLM tách câu (1 request phụ) | hiểu câu phức tạp | +1 request **mỗi câu** (quota + ~0,5 s), khó test, có thể tách sai | Khi heuristic bỏ sót thật |
| LangGraph multi-step (agent tự quyết) | mạnh nhất, đa bước | phức tạp, khó debug, khó đo; over-engineer cho 1 user | Khi cần tool-use/agent thật |
| Không tách | đơn giản | câu nhiều ý trả lời thiếu | Bộ câu hỏi toàn 1 ý |

## Decision

`multi_query.split_question()` tách bằng **regex trên dấu hiệu ngôn ngữ** (`so với`, `and|vs|versus`, `;`,
`đồng thời`, `và`, `,` trước "khi nào/tại sao/như thế nào…"), **không** tách trong backtick/nháy
(`_PROTECTED`) để không phá tên hàm/code. Tối đa `MULTI_QUERY_MAX_PARTS=3`.

Mỗi part retrieve riêng (`_initial_retrieval`), rồi **mỗi part được rerank với đủ `top_n`** trên chunk
**đầy đủ độ dài** (sửa ở KB-5.8 — trước đó chấm trên chunk bị cắt cụt, làm mất bằng chứng).

Lý do loại LLM-split: đo được lợi ích chính **không** đến từ multi-query (xem control run dưới), trong
khi chi phí là 1 request mỗi câu.

## Bằng chứng (số đo thật — gồm cả phần **không** tốt)

| Cấu hình | `hit@k` | `MRR` | `precision@k` | p50 | Run |
|---|---|---|---|---|---|
| Trước multi-query (top-N 20) | 1,0 | 0,975 | 0,533 | 9,70 s | `kb54-before` |
| Sau multi-query (top-N 20) | 1,0 | 0,975 | **0,617** | 6,50 s | `kb54-after` |
| **Control**: top-N 4, multi-query **OFF** | 1,0 | **1,0** | 0,55 | **2,00 s** | `kb54-control-topn4` |
| top-N 4 + multi-query ON | 1,0 | 0,883 | 0,483 | 1,11 s | `kb58-top4-mq-on` |
| **Chốt**: top-N 6, mỗi part đủ dài | 1,0 | 0,975 | **0,617** | **3,44 s** | `kb58-top6-mq-fullpart` |

**Đọc trung thực**: multi-query **chỉ** cải thiện `precision@k` (0,533 → 0,617), **không** cải thiện
`hit@k`/`MRR` (đã bão hoà 1,0/0,975). Đòn bẩy latency lớn hơn là **`RERANK_TOP_N`** (20 → 4–6). Và khi ép
top-N xuống 4 thì bật multi-query lại **làm `MRR` giảm** (1,0 → 0,883) — tức 2 thay đổi không cộng hưởng.

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Tách câu bằng split đơn giản (`split(" và ")`)**: phá tên riêng/tên hàm ("JPA và Hibernate" ổn, nhưng
  "`spring.jpa.hibernate.ddl-auto` và `open-in-view`" thì không) ⇒ phải bảo vệ code/nháy.
- **Rerank từng part trên chunk bị cắt cụt 500 ký tự**: chấm thiếu bằng chứng ⇒ part đúng bị loại. KB-5.8
  sửa: chấm đủ độ dài.
- **Đo mà không có control run**: sẽ kết luận "multi-query làm nhanh 9,7 → 6,5 s" trong khi nguyên nhân
  thật là... top-N (KB-5.4 suýt chốt sai; ADR-0010).
- **Cho LLM tách câu "cho chắc"**: +1 request/câu để đổi thứ đã bão hoà — TD-30 Skip.

## Consequences

- **Được**: câu nhiều ý được phủ đủ (precision +8 điểm %), 0 chi phí thêm, test được bằng unit test.
- **Mất**: không xử lý được câu phức tạp mà không có dấu hiệu rõ ("khác nhau thế nào" không có "và");
  multi-query làm **tăng** số lần rerank (mỗi part một lượt) ⇒ nếu top-N lớn thì latency cộng dồn.
- **Tech debt**: **TD-30** (chưa thử LLM-split) — **Skip** có điều kiện revisit.

## Nếu làm lại thì khác gì

1. Chốt **control run trước** khi code multi-query (bài học KB-5.4/ADR-0010).
2. Gắn **loại câu hỏi** vào bộ vàng để biết multi-query giúp nhóm nào (hiện đo gộp).
3. Ngay từ đầu đặt `multi_query_max_parts` theo **số ý thật** trong câu (hiện cứng 3) và log lại số part
   để biết heuristic có tách đúng không.

## Revisit

Xem lại khi:

- Gặp **≥ 5 câu** trong tuần mà câu trả lời thiếu ý dù `hit@k = 1,0` (dấu hiệu cần split thông minh hơn).
- `precision@k` < 0,55 trên bộ vàng mở rộng.
- Có provider **không giới hạn quota** (lúc đó LLM-split rẻ hơn nhiều) — TD-30.
