# ADR-0011 — Index tăng dần theo hash nội dung (`sync` không clear index)

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) |
| **Ngày** | 2026-11-09 |
| **Liên quan** | KB-5.1, KB-4.10 (guard), TD-13, TD-14 · `architecture.md` §4 · code: `app/services/index_sync.py`, `document_service.py:719` (`sync_documents`) |

## Context

Trước KB-5.1, cách duy nhất để cập nhật index là `POST /documents/refresh` = **clear + embed lại toàn bộ**
⇒ 56 file / 601 chunk mất **~22 phút** (bf16, TD-14) và trong lúc đó **không có index** để trả lời.
Sửa 1 file ghi chú mà phải chờ 22 phút là không dùng được.

Ràng buộc: không thêm hạ tầng (không cron, không queue), chạy được cả lúc startup lẫn bằng 1 nút trên UI.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **So hash nội dung + diff added/updated/removed** (chọn) | chỉ embed file đổi; index cũ vẫn phục vụ trong lúc sync | phải đọc + hash mọi file mỗi lần (~1,5 s/56 file) | ⭐ Tài liệu local, sửa lẻ tẻ |
| So `mtime` + `size` | rẻ hơn hash | copy/restore/`git checkout` đổi mtime ⇒ sync lại toàn bộ; sửa nhanh trong cùng giây có thể lọt | Khi file rất lớn (> 50 MB) |
| Watchdog (inotify) | realtime | thêm process, phức tạp trong Docker/WSL, mất event khi container tắt | Khi cần realtime |
| Clear + re-index toàn bộ | đơn giản, chắc chắn sạch | 22 phút + mất index tạm thời | Cứu hộ khi index hỏng |

## Decision

1. `digest = sha256(nội dung file)[:16]` — **không** dùng mtime/size (đổi tên ≠ đổi digest nhưng `source`
   đổi ⇒ vẫn là removed + added).
2. `diff_indexed()` sinh `SyncPlan(added, updated, removed, unchanged)`; chỉ `added`/`updated` mới embed.
3. **`sync` không clear**: chunk của file đổi bị xoá theo `where={"source": path}` rồi thêm lại; file bị
   xoá trên đĩa ⇒ xoá chunk tương ứng. Trong lúc sync, chat vẫn trả lời bằng index hiện có.
4. **Guard folder rỗng** (bài học KB-4.10): folder không tồn tại / 0 file hỗ trợ ⇒ **không** sync
   (`DocumentsFolderEmptyError` 409), vì nếu không sẽ hiểu là "mọi file đã bị xoá" và **xoá sạch index**.
5. `index_version++` sau mỗi lần đổi index ⇒ cache rerank tự vô hiệu (ADR-0012); corpus BM25 rebuild
   (ADR-0005).

## Bằng chứng (số đo thật)

| Chỉ số | Clear + re-index | Sync tăng dần | Nguồn |
|---|---|---|---|
| 1 file mới (1,2 s/file) | ~22 phút (601 chunk) | **~1,2 s/file** | KB-5.1 |
| Startup khi không đổi gì | ~22 phút (nếu refresh) | **0,029 s** (56 file hashed, 0 embed) | KB-5.14 verify (container) |
| Chat trong lúc sync | **không trả lời được** | trả lời bình thường | KB-5.1 |
| Re-index toàn bộ (khi thật sự cần) | 22 phút (bf16) | **7,3 phút** (fp32, ADR-0003) | KB-5.14 |

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **`sync` = clear + load**: mất index trong 22 phút, và nếu lỗi giữa đường thì index **rỗng** ⇒ chat trả
  lời "không có trong knowledge base" cho mọi câu.
- **Không có guard folder rỗng**: đã xảy ra ở KB-4.10 — `.dockerignore` loại folder `Interview/` ⇒
  container thấy folder rỗng, "sync" hiểu là xoá hết ⇒ mất 601 chunk. Guard là **bắt buộc**, không phải
  nice-to-have.
- **Dùng mtime làm digest**: `git checkout`/copy giữ nội dung nhưng đổi mtime ⇒ embed lại toàn bộ (đúng
  lúc bạn chỉ muốn đổi nhánh).
- **Quên `index_version++`**: cache rerank trả kết quả của tài liệu cũ (ADR-0012) — retrieval "đúng nhưng
  lỗi thời".

## Consequences

- **Được**: sync 1 file ~1 s; chat không bị gián đoạn; startup gần như tức thì khi không đổi gì.
- **Mất**: mỗi lần sync vẫn phải hash **toàn bộ** folder (1,5 s/56 file; tăng tuyến tính theo số file và
  size); không phát hiện thay đổi realtime (phải bấm Đồng bộ hoặc restart).
- **Tech debt**: TD-14 (đã trả — fp32), TD-25 (đã trả — sync nền + trạng thái).

## Nếu làm lại thì khác gì

1. Lưu bảng `file_hash` trong **SQLite** thay vì đọc từ metadata Chroma mỗi lần (hiện `collection.get()`
   toàn bộ để lấy `source`+`file_hash` — 601 chunk thì ổn, 10k chunk sẽ chậm).
2. Thêm **chế độ `--dry-run`** cho `/documents/sync` (trả plan mà không embed) để xem trước.
3. Đưa **tham số chunking + embedding fingerprint** vào diff (hiện đổi `CHUNK_SIZE` mà sync báo
   "unchanged" — bẫy thật, xem ADR-0004).

## Revisit

Xem lại khi:

- Số file **> 500** hoặc tổng dung lượng **> 100 MB** ⇒ thời gian hash vượt 10 s (lúc đó cần cache hash).
- Cần cập nhật **realtime** khi sửa file (→ watchdog hoặc git hook).
- Số chunk **> 10.000** ⇒ phải đổi cách lấy `file_hash` (SQLite như trên).
