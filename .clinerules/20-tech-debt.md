# 20 — Tech debt register (bắt buộc ghi nhận)

Rule behavioral. Mục tiêu: **không để nợ kỹ thuật sống trong đầu ai** — mọi món nợ nằm ở một chỗ,
có **điều kiện revisit**.

## Nguồn sự thật

`Backlog.md` → **§ 7. Technical debt register** (`TD-<số>`). Không tạo file riêng, không ghi trong
comment code (comment bị đọc 1 lần rồi quên; bảng thì còn).

## Khi nào PHẢI ghi một mục nợ

Ghi ngay trong **cùng ticket** phát hiện ra nó khi gặp một trong các trường hợp:

- Chọn giải pháp **đơn giản hơn nhưng biết là chưa đủ** (vd redact PII bằng regex thay vì NER).
- Bỏ qua một việc **đáng ra nên làm** vì ngoài scope (vd chưa có rate limit cho endpoint chat).
- Phát hiện **giới hạn đã biết** (vd ChromaDB local, chưa có job re-index khi doc đổi).
- Cố ý **hoãn** một rủi ro vận hành (vd conversation lưu in-memory, mất khi restart).
- Copy-paste đoạn code đáng ra phải dùng chung.

**Không** ghi: việc đã có ticket mở cho nó (trùng), hoặc sở thích cá nhân.

## Format một mục (bảng trong `Backlog.md` § 7)

| Cột | Nội dung |
|---|---|
| `ID` | `TD-<số>` — tăng dần, **không tái sử dụng** |
| `Mô tả` | 1 câu nêu **vấn đề** (không nêu giải pháp dài dòng) |
| `Nguồn` | Ticket phát hiện (vd `KB-1.1`) |
| `Điều kiện revisit` | **Bắt buộc**, verify được bằng dữ liệu/sự kiện |
| `Mức độ` | `thấp` / `trung bình` / `cao` |

## Khi nào trả nợ

- Không gộp việc trả nợ **thay đổi code** vào ticket khác — phải ticket riêng.
- Trả xong → đổi `Mức độ` thành `✅ đã trả (<ticket>)` và **giữ dòng**.
- Rà bảng **cuối mỗi phase**.

## Liên quan

- `AGENTS.md` §4 (quy trình ticket) · §9 (việc không được làm)
- `Backlog.md` § 7 (bảng nợ) · § 6 Learning log (bài học, khác mục đích)
