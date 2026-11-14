# 10 — Git workflow (bắt buộc)

Rule behavioral. Base convention ở `AGENTS.md` §6. Vòng đời đóng ticket đã **gộp vào `/run-ticket.md`**.

## Đặc thù: 1 repo duy nhất (monorepo)

- BE (`Knowledge-base/`), FE (`Knowledge-base-fe/`) và tài liệu/AI assets ở gốc **cùng một git repo**
  (`origin` → GitHub). Không còn 3 repo GitLab, không còn `sync.sh`.
- Một ticket đụng cả BE + FE → **một nhánh, một PR**; commit message nhắc **cùng ticket ID**.
- Không commit file trong `Interview/` (đã ignore) hay `.env*`.

## CI: GitHub Actions

- Workflow [`.github/workflows/tests.yml`](../.github/workflows/tests.yml): `backend (pytest)` +
  `frontend (vitest + typecheck + lint)`.
- Chạy mỗi push/PR vào `main`. **PR đỏ ⇒ không merge.** Không còn `CI_ENABLED` / pipeline GitLab.

## Mô hình: GitHub Flow

- `main` **luôn** chạy được. **Không** commit thẳng `main`.
- Mỗi ticket → nhánh ngắn hạn → PR → squash merge → xoá nhánh.

## Vòng đời 1 ticket (đã gộp vào `/run-ticket.md`)

1. Tạo nhánh `<type>/<ticket-id>-<slug>` từ `main` mới nhất (`type` ∈ feat, fix, docs, refactor, test, chore).
2. **Commit** Conventional Commits nhắc ticket ID; gộp cả **mark-done docs** vào commit cuối.
3. **Push** nhánh lên `origin` (SSH — đã xác nhận có quyền push).
4. **Tạo PR** vào `main`.
5. **Merge (squash) + xoá nhánh** khi đủ điều kiện (CI xanh + không conflict).
6. Cập nhật `main` local + **kiểm `main` thật sự có nội dung mới**.

## Tạo & merge PR (thứ tự ưu tiên)

1. **`gh` (GitHub CLI)** — nếu đã cài & đã auth:
   ```bash
   gh pr create --base main --head <branch> \
     --title "<type>(scope): ..." --body "<summary + lệnh verify>"
   gh pr merge <id> --squash --delete-branch
   ```
2. **Fallback**: push nhánh rồi mở PR trên web GitHub
   (`https://github.com/anchu3003/knowledge-base/compare/main...<branch>`).

> Kiểm nhanh: `gh auth status`. Chưa auth → `gh auth login` (scope `repo`, `workflow`).


## An toàn

- **Không** force-push lên `main`. **Không** commit thẳng `main`.
- Nhánh chính tên `main`.
- **Không** commit secret / token / connection string / PII (`.clinerules/30-pii-safety.md`).

