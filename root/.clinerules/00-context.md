# 00 — Context loader (Memory Bank lite)

Rule phụ trợ. **Nguồn sự thật vẫn là `AGENTS.md`** — không lặp nội dung ở đây để tránh trùng/lệch.

## Khi bắt đầu một task

Đọc theo thứ tự:

1. `AGENTS.md` — working agreement (ngôn ngữ, nguyên tắc, convention, DoR/DoD, PII rule).
2. `architecture.md` — kiến trúc, tech stack, luồng dữ liệu, roadmap, glossary.
3. `Backlog.md` — ticket đang làm / tiếp theo, learning log, tech debt, changelog.

Không tạo `memory-bank/` riêng. `architecture.md` + `Backlog.md` đóng vai **Memory Bank**.

## Bản đồ repo

| Thư mục | Vai trò | Stack | Git remote |
|---|---|---|---|
| `Knowledge-base/` | Backend API (RAG) | Python 3.11 · FastAPI · LangChain · ChromaDB | `gitlab.com:anchu3003/knowledge-base-be` |
| `Knowledge-base-fe/` | Frontend UI | Next.js 16 · React 19 · Tailwind v4 · Radix/shadcn | `gitlab.com:anchu3003/knowlege-base-fe` |
| `.clinerules/`, `.cline/`, `tools/` | AI assets + script hỗ trợ | — | (không commit secret) |

> 2 thư mục là **2 git repo riêng** (GitLab). Root `Kb-khoa-hoc` **không** phải git repo — AI assets nằm ở root, không commit vào repo con.

## Nhắc nhanh (chi tiết xem `AGENTS.md`)

- Mỗi lượt chỉ làm **1 ticket** trong `Backlog.md` — không build một loạt.
- Trả lời **tiếng Việt**, giữ keyword tiếng Anh (`AGENTS.md` §2).
- **PII rule** (`AGENTS.md` §9.5): filter email/sđt/mật khẩu/API key **trước khi** gửi lên LLM.
- Quyết định lớn → ADR trong `docs/adr/` + update `architecture.md`.
- Không claim "đã test" khi chưa chạy thật.

## AI assets đang có

| Loại | Vị trí | Gọi bằng |
|---|---|---|
| Rule | `.clinerules/10-git-workflow.md` | luôn active (commit sau mỗi ticket, nhánh, PR) |
| Rule | `.clinerules/20-tech-debt.md` | luôn active (ghi tech debt vào `Backlog.md` §7) |
| Rule | `.clinerules/30-pii-safety.md` | luôn active (che PII trước khi gửi LLM / commit) |
| Skill | `.cline/skills/kb-ticket` | auto khi tạo/sửa ticket, hoặc `/kb-ticket` |
| Skill | `.cline/skills/kb-verify` | auto khi verify, hoặc `/kb-verify` |
| Skill | `.cline/skills/kb-adr` | auto khi viết ADR, hoặc `/kb-adr` |
| Skill | `.cline/skills/kb-pii-redaction` | khi làm việc với PII redaction, hoặc `/kb-pii-redaction` |
| Workflow | `.clinerules/workflows/new-ticket.md` | `/new-ticket.md` (breakdown epic + Q&A) |
| Workflow | `.clinerules/workflows/run-ticket.md` | `/run-ticket.md` (thực thi + đóng ticket, gồm git) |
