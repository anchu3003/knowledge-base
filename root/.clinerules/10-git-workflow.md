# 10 — Git workflow (bắt buộc)

Rule behavioral. Base convention ở `AGENTS.md` §6. Vòng đời đóng ticket đã **gộp vào `/run-ticket.md`**.

## Đặc thù: 3 repo (2 app repo + root docs repo)

- `Knowledge-base/` và `Knowledge-base-fe/` là **2 git repo GitLab độc lập** (remote SSH, xem `git remote -v`
  trong từng repo — dạng `gitlab.com:anchu3003/<repo>.git`).
- **Root là 1 git repo riêng** (từ 2026-11-10): track `AGENTS.md`, `architecture.md`, `Backlog.md`, `README.md`,
  `docs/`, `tools/`, `.cline*`; **ignore** 2 folder repo con. Commit tài liệu root bằng
  `git -C <root> commit ...` — cùng commit message + ticket ID, nhưng **không** tạo MR (chưa có remote).
- Một ticket đụng **cả 2 repo** → tạo **2 nhánh cùng tên** + **2 MR**.
- Commit message cả 2 repo đều nhắc **cùng ticket ID**.

## Đặc thù: CI có sẵn nhưng TẮT mặc định (KB-5.7)

- 2 repo đã có `.gitlab-ci.yml` nhưng **gate `CI_ENABLED`** — chưa đặt biến CI/CD ⇒ **không** tạo pipeline ⇒ hiện **không có bước chờ pipeline**.
- Hệ quả:
  - Không dùng `[skip ci]` (vô nghĩa khi không có pipeline).
  - "Điều kiện merge" = **ticket `Done` (đã verify) + MR có summary + không conflict** — không có điều kiện CI.
  - **Khi bật `CI_ENABLED=true`** → bổ sung điều kiện "pipeline xanh" vào `/run-ticket.md` `<merge_conditions>`.

## Mô hình: GitHub Flow

- `main` **luôn** chạy được. **Không** commit thẳng `main`.
- Mỗi ticket → nhánh ngắn hạn → MR → squash merge → xoá nhánh.

## Vòng đời 1 ticket (đã gộp vào `/run-ticket.md`)

1. Tạo nhánh `<type>/<ticket-id>-<slug>` từ `main` mới nhất (`type` ∈ feat, fix, docs, refactor, test, chore).
2. **Commit** Conventional Commits nhắc ticket ID; gộp cả **mark-done docs** vào commit cuối.
3. **Push** nhánh lên `origin` (SSH — đã xác nhận có quyền push).
4. **Tạo MR** vào `main`.
5. **Merge (squash) + xoá nhánh** khi đủ điều kiện (không chờ CI).
6. Cập nhật `main` local + **kiểm `main` thật sự có nội dung mới**.

## Tạo & merge MR (thứ tự ưu tiên)

1. **`glab` (GitLab CLI)** — nếu đã cài:
   ```bash
   glab mr create --source-branch <branch> --target-branch main \
     --title "<...>" --description "<...>" --remove-source-branch --yes
   glab mr merge <id> --squash --remove-source-branch --yes
   ```
2. **GitLab push options** (khi không có `glab`) — tự tạo MR ngay lúc push:
   ```bash
   git push -o merge_request.create -o merge_request.target=main \
     -o merge_request.remove_source_branch -o merge_request.title="<type>(scope): ..." \
     origin <branch>
   # (tạo MR; bước MERGE vẫn cần glab / API token / web)
   ```
3. **Fallback**: push nhánh → merge trên web GitLab (link `/-/merge_requests/new`).

> Ghi chú môi trường: máy này **đã cài `glab` v1.128.0** (`C:\Users\anchu\AppData\Local\Programs\glab\glab.exe`).
> Cần **auth 1 lần** (token cho REST API, không phải SSH):
> ```bash
> glab auth login --hostname gitlab.com --token <PAT>   # PAT scope: api
> ```
> Chưa auth → `glab` trả `401` khi tạo/merge MR. Kiểm bằng `glab auth status`.


## An toàn

- **Không** force-push lên `main`. **Không** commit thẳng `main`.
- Nhánh chính tên `main`.
- **Không** commit secret / token / connection string / PII (`.clinerules/30-pii-safety.md`).

