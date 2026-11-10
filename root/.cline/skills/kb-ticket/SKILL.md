---
name: kb-ticket
description: Tạo mới hoặc cập nhật ticket trong Backlog.md của dự án Knowledge Base theo format BA-style (Bối cảnh → Mục tiêu → In scope → Out of scope → Acceptance Criteria → Ghi chú kỹ thuật → Kết quả verify → Learning note) kèm checklist DoR/DoD. Dùng khi breakdown epic thành ticket chi tiết hoặc khi tạo/sửa ticket.
---

# Ticket Knowledge Base (BA-style)

## Convention (`AGENTS.md` §7)

- **ID**: `KB-<phase>.<số>` — ví dụ `KB-0.1`, `KB-1.3`. Không đổi ID sau khi tạo.
- **Trạng thái**: `Todo` → `In Progress` → `Review` → `Done` (hoặc `Blocked` + lý do).
- **Ước lượng**: `S` (< nửa ngày) / `M` (1–2 ngày) / `L` (3–5 ngày). Nếu `L` → **phải tách nhỏ**.
- Viết như **BA đã define xong**: mô tả được, verify được, không mơ hồ.
- Phase xa chỉ để mức **epic**; chỉ breakdown khi tới lượt.
- Ticket đụng cả BE + FE → ghi rõ **repo** trong "Ghi chú kỹ thuật".

## Thứ tự mục bắt buộc

1. Bảng `Trường | Giá trị` (Trạng thái / Phase / Repo / Phụ thuộc / Ước lượng)
2. Bối cảnh
3. Mục tiêu
4. In scope
5. Out of scope
6. Acceptance Criteria (checklist `- [ ]`, verify được)
7. **Q&A (câu hỏi cho user trả lời TRƯỚC khi làm)** — đánh số `Q1, Q2…`, mỗi câu có dòng `→ ` trống
8. Ghi chú kỹ thuật (pattern / thư viện / trade-off đã chấp nhận)
9. Kết quả verify *(điền khi Done)*
10. Learning note *(điền khi Done)*

## Q&A — quy tắc

- Chỉ liệt kê câu hỏi **không suy ra được từ doc/code** và **ảnh hưởng design/scope/nghiệm thu**.
- Cái suy ra được → tự quyết + ghi **"Giả định"**, KHÔNG biến thành câu hỏi.
- KHÔNG tự bịa câu trả lời. User trả lời xong mới chạy `/run-ticket.md`.
- Câu hỏi nảy sinh **giữa lúc làm** (không nghĩ ra lúc plan) vẫn được hỏi — đó là câu hỏi thực sự cần.


## Checklist DoR — chỉ bắt đầu khi đủ

- [ ] Bối cảnh & mục tiêu (why) rõ
- [ ] Scope rõ: in / out
- [ ] Acceptance Criteria dạng checklist, verify được
- [ ] Phụ thuộc: ticket nào phải xong trước
- [ ] Ghi chú kỹ thuật: pattern + trade-off chấp nhận

## Checklist DoD (`AGENTS.md` §5)

- [ ] Code chạy, pass lint + format
- [ ] Có test (unit bắt buộc; integration nếu có I/O)
- [ ] Đã verify bằng lệnh thật + dán output vào ticket
- [ ] Không hard-code secret / connection string; config qua env
- [ ] **Không rò PII/secret ra ngoài** (`.clinerules/30-pii-safety.md`)
- [ ] `Backlog.md` update status + learning note
- [ ] Doc/README update nếu cách chạy thay đổi

## Khi tạo / sửa ticket

- Cập nhật bảng **Trạng thái theo phase** (số Done / tổng).
- Cập nhật header: **Ticket đang làm** / **Ticket tiếp theo**.
- Thêm dòng vào **Changelog**.
- Mơ hồ ảnh hưởng design → **hỏi user trước**, không đoán.
