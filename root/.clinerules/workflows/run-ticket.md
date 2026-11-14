# /run-ticket.md — Thực thi + ĐÓNG 1 ticket (gộp close-ticket + auto git workflow)

<task_objective>
Thực thi **đúng một** ticket theo Read → Plan → Build → Verify → Document → Report, rồi **đóng ticket
luôn** trong cùng lượt: commit → push → tạo MR → merge (squash) khi đủ điều kiện. Project **KHÔNG có
CI/CD** nhưng **TẮT mặc định** (`CI_ENABLED`) → không có bước chờ pipeline.
</task_objective>

<preconditions>
- Ticket đã có mục **Q&A** và user **ĐÃ trả lời** (chưa trả lời → hỏi, KHÔNG tự đoán).
- Xác định repo sẽ đụng: BE `Knowledge-base` / FE `Knowledge-base-fe` / cả hai (`10-git-workflow.md`).
</preconditions>

<detailed_sequence_of_steps>
1. **Read**: đọc ticket + phần liên quan trong `architecture.md` + code liên quan.
2. **Plan**: tóm tắt cách hiểu, list bước, nêu giả định. Nếu nảy sinh câu hỏi **thực sự cần**
   (không thể nghĩ ra lúc plan) → hỏi user, không đoán.
3. **Build**: code theo convention. Đụng dữ liệu gửi ra LLM → áp redaction PII (rule `30-pii-safety.md`).
4. **Verify**: chạy lệnh thật (skill `kb-verify`), **dán output thật**. Fail → không đánh Done.
5. **Document**: cập nhật `Backlog.md` (status `Done` + Kết quả verify + Learning note + bảng phase +
   Learning log + Changelog); `architecture.md` nếu design đổi; ghi tech debt §7 nếu có.
6. **Git — đóng ticket (mỗi repo bị đụng):** (chi tiết ở `.clinerules/10-git-workflow.md`)
   a. Tạo nhánh `<type>/<ticket-id>-<slug>` từ `main` mới nhất.
   b. Commit **Conventional Commits**, nhắc ticket ID, gộp cả mark-done docs vào commit cuối.
   c. Push nhánh lên `origin`.
   d. Tạo **MR** vào `main` (glab nếu có → fallback GitLab API/push-option; xem `10-git-workflow.md`).
   e. **Merge (squash) + xoá nhánh khi đủ điều kiện** (bên dưới) — không chờ CI.
   f. Sau merge: cập nhật `main` local + **kiểm `main` thật sự có nội dung mới**.
7. **Report**: tổng kết — đã làm gì, file nào, lệnh verify + output, link MR/merge, phần chưa làm / tech debt.

**Chỉ làm 1 ticket mỗi lượt** (`AGENTS.md` §3.1). Không gộp ticket mới.
</detailed_sequence_of_steps>

<merge_conditions>
Đủ cả 3 thì merge tự động (không hỏi lại):
1. Ticket `Done` — đã verify thật, output dán trong ticket.
2. MR có **mô tả/summary** (tóm tắt + lệnh verify).
3. **Không conflict** với `main`.

Chưa có điều kiện CI: 2 repo **có** `.gitlab-ci.yml` nhưng gate `CI_ENABLED` (mặc định chưa đặt ⇒ không tạo pipeline). Khi bật `CI_ENABLED=true` → bổ sung điều kiện "pipeline xanh" ở đây.
</merge_conditions>

