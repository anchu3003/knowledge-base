# ADR-0017 — Môi trường dev: WSL2 + `uv`/`fnm` (user-space) + docker engine native

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) · TD-9 đã trả, TD-24 mở (Skip) |
| **Ngày** | 2026-11-09 |
| **Liên quan** | KB-7.1, KB-5.10 (image 16,5 → 2,68 GB), TD-6 (đã trả), TD-9 (đã trả), TD-24 (Skip) · `AGENTS.md` §6 · `tools/setup-wsl-docker-engine.sh` |

## Context

Ban đầu code nằm trên Windows (`D:\…`) và mọi thứ chạy qua Docker Desktop + tool Windows. 3 vấn đề đo được:

1. **Chậm**: `node_modules` + `torch` trên `/mnt/d` chậm gấp nhiều lần ổ đĩa Linux (mỗi `npm ci`/build
   lâu hơn hẳn); file watcher của Next.js không hoạt động ổn định trên ổ Windows.
2. **Hai môi trường lệch nhau**: Python/Node cài trên Windows, còn container chạy Linux ⇒ "chạy trên máy
   được, trong Docker không" (và ngược lại).
3. **Docker Desktop**: cần license với công ty lớn, cập nhật hay phá WSL integration, khó hiểu khi
   `docker info` trỏ về `\\wsl$`.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **WSL2 + tool user-space (`uv`, `fnm`) + docker engine native trong WSL** (chọn) | Linux thật (perf + watcher); không `sudo apt` cho Python/Node; docker không qua Desktop | phải nhớ "mở terminal WSL"; Windows tool (glab/Node) thành thừa | ⭐ Máy dev Windows, muốn Linux |
| Giữ Windows + Docker Desktop | quen, có GUI | chậm trên `/mnt/*`; lệch môi trường; Desktop integration hay hỏng | Khi phải dùng tool Windows-only |
| Linux native / dual boot | nhanh nhất | mất tiện ích Windows (Office, game…) | Máy chỉ để dev |
| Dev container / Codespaces | tái lập tốt | cần mạng, tốn phí, chậm IO với repo lớn | Team nhiều người |

## Decision

1. Code đặt trên **Linux FS** (`~/projects/kb-khoa-hoc`), **không** `/mnt/c|/mnt/d`.
2. **`uv`** cho Python 3.13 (venv `.venv`), **`fnm`** cho Node LTS — cả hai cài **user-space**, không cần
   `sudo apt`.
3. **Docker engine native trong WSL** (`systemd=true` + `systemctl enable --now docker`), **bỏ** Docker
   Desktop integration (script `tools/setup-wsl-docker-engine.sh`).
4. **EOL** thống nhất LF: `.gitattributes` (`* text=auto eol=lf`) + `core.autocrlf=input` — trước đó 2 repo
   "dirty toàn bộ" chỉ vì CRLF.
5. Trong image: **torch bản CPU-only** + `.dockerignore` chặn `.env`; model HF để trong **volume** (không
   bake) — xem bảng dưới.

## Bảng: thành phần → cài trong WSL → version

| Thành phần | Cài trong WSL | Version hiện tại | Ghi chú |
|---|---|---|---|
| Python | `uv python install 3.13` → `uv venv --python 3.13 .venv` | **3.13.18** | Không dùng Python của Windows |
| Node | `fnm install --lts` (fnm ở `~/.local/share/fnm`) | **v26.13.0** · npm 11.20 | Next.js 16 cần Node ≥ 20 |
| Docker | engine native + `systemd` | **29.9.x** | `docker info` → `Docker Root Dir /var/lib/docker` |
| GitLab CLI | `glab auth login --token <PAT scope api>` | **1.128.0** | Token **không** commit |
| SSH GitLab | `~/.ssh/id_ed25519` | — | Public key add trên GitLab |
| Playwright | `tools/setup-playwright.sh` (không `sudo`) | `@playwright/test ^1.65` | Lib X11 tải bằng `dpkg -x` vào `~/.local/pw-libs` |

## Bằng chứng (số đo thật)

| Kiểm chứng | Kết quả | Nguồn |
|---|---|---|
| Test BE trong WSL | **320 passed** | `.venv/bin/python -m pytest -q` |
| Build FE | `Compiled successfully in 2.4 s` | `npm run build` |
| Docker build BE | OK, image **2,68 GB** (trước **16,5 GB**, −83,8%) | KB-5.10 |
| Gói `nvidia-*` trong image | **0** (torch CPU-only) | KB-5.10 |
| `.env` trong image | **không có** (`.dockerignore`) | KB-7.1 |
| EOL | 2 repo sạch sau khi set `eol=lf` | KB-7.1 |
| Playwright e2e | **16 passed** (~17 s), Chromium native, không `sudo`, không Windows relay | KB-4.9 + KB-5.17 |

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Code trên `/mnt/c`**: build FE chậm nhiều lần; watcher bỏ event ⇒ sửa file không hot-reload (dễ tưởng
  "dev server hỏng").
- **Docker Desktop + WSL integration**: `docker` trong WSL trỏ về engine Windows qua socket ⇒ volume/đường
  dẫn khác, và Desktop hay reset integration sau update.
- **`sudo apt install python3`**: bản Python của distro bị hệ thống quản; `uv` giữ mọi thứ trong `~` ⇒
  xoá/đổi version không ảnh hưởng hệ điều hành.
- **Bake model HF vào image**: image +3,3 GB (TD-24) — với 1 máy thì volume + lần tải đầu rẻ hơn nhiều.
- **Không có `.dockerignore` cho `.env`**: secret lọt vào layer (không xoá được bằng `RUN rm` về sau).

## Consequences

- **Được**: tốc độ như Linux thật; 1 môi trường (dev == container); image nhỏ 6×; e2e chạy native.
- **Mất**: phải mở terminal WSL (VS Code Remote-WSL lo phần editor); tool Windows (glab/Node cũ) thành
  thừa nhưng vẫn giữ (Q3 KB-7.1 = không gỡ).
- **Tech debt**: **TD-24** (chưa có registry/deploy, model không bake) — **Skip** tới khi có VPS; xem
  thêm ADR-0011/ADR-0012 về hệ quả single-process.

## Nếu làm lại thì khác gì

1. Migrate sang WSL **trước** Phase 2 (đã phải làm lại vài lần build chậm/không rõ nguyên nhân trên
   `/mnt/d`).
2. Pin version tool bằng file (`uv` có `.python-version`, `fnm` có `.node-version`) ngay từ đầu — hiện
   version nằm trong tài liệu, dễ lệch.
3. Dùng torch CPU-only **ngay lần build image đầu** (16,5 GB → 2,68 GB là bài học đắt: mỗi lần build/pull
   chậm, và `COPY --from=builder` không xoá được layer cũ — phải `RUN --mount=type=bind`).

## Revisit

Xem lại khi:

- Có **VPS/nơi deploy** thật (→ TD-24: registry + CI build + deploy, lúc đó cân nhắc bake model).
- Cần CI chạy e2e (image Playwright chính thức) — đã có `.gitlab-ci.yml` gate `CI_ENABLED` (KB-5.7).
- Cần chạy **> 1 máy dev** (→ dev container hoặc Nix) để khỏi lệch version.
