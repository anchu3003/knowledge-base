# ADR-0004 — Chunking: markdown-aware theo heading, giữ `heading_path`

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-08 |
| **Liên quan** | KB-2.x (chunking), KB-2.4 (re-index) · `architecture.md` §4 · code: `app/services/document_service.py:246-280` · `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=200` |

## Context

Nguồn là ghi chú Markdown nhiều tầng heading (`##`, `###`) trộn file PDF/DOCX. Hai vấn đề thực tế:

1. Cắt theo **ký tự** (RecursiveCharacterTextSplitter thuần) làm chunk **mất ngữ cảnh**: một đoạn nằm
   dưới `## Compare JPA, Spring Data JPA and Hibernate` nhưng khi retrieve chỉ còn câu văn trơ — câu trả
   lời trích dẫn sai chủ đề.
2. Chunk quá lớn ⇒ rerank chậm + tốn context; quá nhỏ ⇒ mất bằng chứng (bản đầu cắt cứng còn làm **mất
   nửa bằng chứng** với `chunk_size=1000`).

Số liệu tham chiếu: 56 file → **601 chunk** (trung bình ~10,7 chunk/file).

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Markdown heading trước, rồi cắt theo size** (chọn) | Chunk không vượt ranh giới mục; giữ `heading_path` để trả lời "đoạn này thuộc mục nào" | File không có heading ⇒ thoái hoá về cắt theo size | ⭐ Tài liệu có cấu trúc |
| Cắt thuần theo ký tự (`RecursiveCharacterTextSplitter`) | Đơn giản, size đều | Mất ngữ cảnh heading; chunk có thể bắt đầu giữa 2 mục | File text/PDF thuần |
| Semantic chunking (theo embedding) | Ranh giới "đúng nghĩa" | Tốn 1 lần embed cho mỗi lần thử; khó debug; chưa có số chứng minh tốt hơn | Khi retrieval kém dù đã có heading |
| Cả file là 1 chunk | Không mất ngữ cảnh | Vượt context, rerank cực chậm, precision giảm | Tài liệu rất ngắn (< 1 trang) |

## Decision

**2 tầng**: `MarkdownHeaderTextSplitter` (theo `#/##/###`) → mỗi section được cắt tiếp bằng
`RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)`; metadata mỗi chunk giữ
`heading_path` dạng `"Cha > Con"` + `source` + `chunk_id`.

`MarkdownHeaderTextSplitter` **không** giới hạn size ⇒ bắt buộc split lại (comment `document_service.py:256`).
Chunk theo section cũng là đơn vị tự nhiên cho multi-query/rerank: mỗi phần câu hỏi chấm đủ top-N
(ADR-0013).

## Bằng chứng (số đo thật)

| Chỉ số | Trước | Sau | Nguồn |
|---|---|---|---|
| Chunk / file | — | 601 chunk / 56 file (~10,7) | `collection_count: 601` (`eval/runs/`) |
| `distinct_file_ratio` (đa dạng nguồn) | 0,707 | 0,733–0,783 | baseline vs `kb22-dedup`, `kb58-*` |
| `hit@k` bộ vàng 20 câu | 0,933 (15 câu, k=5) | 1,0 | `kb25-final` → `kb58-*` |
| Lỗi "mất nửa bằng chứng" | có (bản cắt cứng) | hết | comment `config.py:166` |

`heading_path` là thứ **chỉ** có khi chunk theo heading — dùng để nhóm nguồn khi trả lời (panel Nguồn)
và để debug "vì sao chunk này được chọn".

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Split theo heading rồi quên giới hạn size**: một mục dài 8.000 ký tự thành 1 chunk ⇒ rerank ăn hết
  context window và câu trả lời bị cắt.
- **Overlap = 0**: câu trả lời nằm vắt qua ranh giới 2 chunk ⇒ cả 2 đều thiếu ý.
- **Đổi `CHUNK_SIZE` mà không re-index**: `file_hash` (ADR-0011) chỉ theo **nội dung file**, không theo
  tham số chunk ⇒ sync sẽ nói "unchanged" và index giữ chunk cũ. Đây là bẫy thật: đổi chunking phải
  `DELETE /documents/clear` rồi sync lại.

## Consequences

- **Được**: chunk có ngữ cảnh; câu trả lời trích dẫn đúng mục; `heading_path` dùng lại cho UI.
- **Mất**: file PDF/DOCX không có heading ⇒ hiệu quả thấp hơn Markdown; số chunk/file không đều ⇒
  `MAX_CHUNKS_PER_FILE=2` (dedup) cần thiết để tránh 1 file chiếm hết top-k.
- **Tech debt**: `CHUNK_SIZE`/`CHUNK_OVERLAP` không nằm trong "fingerprint" của index ⇒ đổi là phải nhớ
  re-index tay (xem TD mới ở mục "Nếu làm lại").

## Nếu làm lại thì khác gì

1. Đưa **tham số chunking** vào fingerprint index (cùng chỗ `embedding_fingerprint`) để sync tự phát hiện
   "đổi cách chunk" và đề nghị re-index.
2. Thử **cắt theo token** thay vì ký tự (chunk 1.000 ký tự tiếng Việt ≈ 250–300 token, khá nhỏ so với
   context 128K — có thể tăng lên 1.500 ký tự để giảm số chunk mà vẫn vừa rerank).
3. Lưu `section_title` riêng (không chỉ `heading_path` dạng chuỗi) để filter theo mục.

## Revisit

Xem lại khi:

- `precision@k` < 0,55 hoặc câu trả lời thường xuyên thiếu ý dù `hit@k = 1,0` (dấu hiệu chunk quá nhỏ).
- Số chunk **> 2.000** ⇒ rerank/sync chậm, cần tăng `CHUNK_SIZE` hoặc lọc bớt file.
- Tài liệu không phải Markdown chiếm **> 50%** khối lượng ⇒ cân nhắc pipeline riêng cho PDF/DOCX.
