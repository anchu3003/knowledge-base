# /new-ticket.md — Breakdown epic thành ticket (+ Q&A planning)

<task_objective>
Breakdown một epic (hoặc mô tả tính năng) thành **ticket chi tiết** đúng format `Backlog.md`,
viết như BA đã define xong, VÀ kèm mục **Q&A** — danh sách câu hỏi user trả lời **TRƯỚC khi làm**.
</task_objective>

<detailed_sequence_of_steps>
1. Đọc `AGENTS.md` §7 + template ticket trong `Backlog.md` § 2 + epic liên quan.

2. Sinh ticket theo đúng thứ tự mục: Bối cảnh → Mục tiêu → In scope → Out of scope →
   Acceptance Criteria → **Q&A (câu hỏi cho user trả lời trước)** → Ghi chú kỹ thuật →
   Kết quả verify → Learning note.

3. **Q&A — trọng tâm của flow này:**
   - Liệt kê các câu hỏi **không đọc được từ doc/code** và **ảnh hưởng tới design/scope/nghiệm thu**.
   - Đánh số `Q1, Q2, ...`; mỗi câu để trống phần `→ ` cho user điền.
   - **Chỉ hỏi cái thực sự cần.** Cái suy ra được thì tự quyết và ghi vào **"Giả định"** (không biến
     thành câu hỏi). Tránh hỏi vặt / hỏi thứ đã có trong tài liệu.
   - KHÔNG tự bịa câu trả lời cho Q&A.
   - **Chờ user trả lời Q&A rồi mới chạy `/run-ticket.md`.** Câu hỏi nảy sinh khi ĐANG làm
     (không nghĩ ra lúc plan) thì được phép hỏi giữa chừng — đó là câu hỏi thực sự cần thiết.

4. ID dạng `KB-<phase>.<số>`, không đổi ID cũ; ước lượng `S`/`M`/`L`; nếu `L` → tách nhỏ.
   Ghi rõ **repo** (BE `Knowledge-base` / FE `Knowledge-base-fe` / cả hai).

5. Đặt ticket vào đúng phase trong `Backlog.md`; cập nhật bảng "Trạng thái theo phase",
   header (Ticket tiếp theo), và Changelog.

6. Không breakdown phase xa thành ticket chi tiết khi chưa tới lượt.
</detailed_sequence_of_steps>

