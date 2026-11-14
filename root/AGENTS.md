# AGENTS.md — Working agreement cho repo Kb-khoa-hoc

> Đây là "hợp đồng làm việc" giữa **bạn (human)** và **AI agent (Cline)** trong repo này.
> Đọc file này trước khi làm bất cứ việc gì. Mọi thay đổi về cách làm việc đều update vào đây.

---

## 1. Repo này là gì

Đây là **knowledge base cá nhân** của tôi (không phải sản phẩm cho team nữa) — một hệ **RAG chatbot**
để hỏi đáp trên tài liệu cá nhân: ghi chú kỹ thuật, học tiếng Anh, ôn phỏng vấn, tài liệu tự học.

- **Lịch sử mục tiêu (đã đổi):** ban đầu là bài tập nhóm khi học AI, mục tiêu *onboard member mới*.
  Nay chuyển thành **knowledge base cá nhân**. Onboarding chỉ còn là *một* use case.
- Ưu tiên **học đúng + dùng được cho bản thân**, không ship nhanh.
- Người thực hiện: **bạn + AI**. Không chia role Lead/DevOps/QA — cả hai cùng làm design → code → test.

Ba repo (2 repo app trên GitLab + 1 repo root chỉ track tài liệu/AI assets):

| Thư mục | Vai trò | Stack | Remote |
|---|---|---|---|
| `Knowledge-base/` | Backend RAG API | Python 3.13 · FastAPI · LangChain · ChromaDB · sentence-transformers | `knowledge-base-be` |
| `Knowledge-base-fe/` | Frontend UI | Next.js 16 · React 19 · Tailwind v4 · Radix/shadcn | `knowlege-base-fe` |
| `./` (root) | Tài liệu + AI assets + tools | Markdown, Python tool nhỏ | local `main` (chưa có remote) |

Root repo **ignore** 2 folder repo con (`.gitignore`) ⇒ không file nào bị track 2 lần.


Tài liệu nguồn (source of truth):

| File | Nội dung |
|---|---|
| `architecture.md` | Kiến trúc, luồng dữ liệu, tech stack, roadmap, glossary |
| `Backlog.md` | Ticket **đang làm / sắp làm** chia theo phase, thực hiện cuốn chiếu |
| `AGENTS.md` | File này — cách làm việc |
| `docs/adr/` | Architecture Decision Record cho quyết định lớn |

---

## 2. Ngôn ngữ & văn phong

| Quy tắc | Chi tiết |
|---|---|
| Ngôn ngữ tài liệu | **Tiếng Việt** |
| Thuật ngữ kỹ thuật | **Giữ nguyên tiếng Anh**, không dịch |
| Code, tên biến, commit message | **Tiếng Anh** |
| Văn phong | Như dev Việt nói chuyện: thẳng, ngắn, thực dụng. Ưu tiên bullet/bảng. Tránh văn phong hành chính dịch máy. |
| Ví dụ | Luôn có ví dụ cụ thể (số liệu, request flow, đoạn code, lệnh chạy) |

**Keyword giữ tiếng Anh** (ví dụ, không giới hạn): `RAG`, `retrieval`, `embedding`, `chunking`,
`re-ranking`, `trade-off`, `latency`, `throughput`, `rate limit`, `quota`, `streaming (SSE)`,
`redaction`, `PII`, `vector store`, `similarity search`, `context window`, `hallucination`,
`hybrid search`, `BM25`, `token usage`.

---

## 3. Nguyên tắc làm việc (BẮT BUỘC)

### 3.1. Làm cuốn chiếu, tuyệt đối không làm một loạt

- Mỗi lượt chỉ làm **1 ticket** trong `Backlog.md` (hoặc 1 nhóm rất nhỏ cùng phase).
- **Không** scaffold nhiều feature trong 1 lần rồi để "chạy sau".
- **Không code trước ticket.** Muốn làm gì → tạo/sửa ticket trước, chốt nội dung, rồi mới code.
- Sau mỗi ticket: chạy được + có test + update `Backlog.md` + ghi lại cái học được.

### 3.2. Đi theo vertical slice, không đi ngang

- Xong 1 tính năng phải **end-to-end chạy được**: UI → API → service → vector store → LLM → response.
- Không kiểu "hôm nay code xong tầng repository của mọi service".

### 3.3. Mọi quyết định lớn phải có lý do

- Chọn giải pháp nào phải nói rõ: **tại sao**, **trade-off**, **khi nào revisit**.
- Thay đổi lớn (đổi LLM provider, embedding model, vector store, kiến trúc RAG) → viết ADR
  trong `docs/adr/` + update `architecture.md`.

### 3.4. Không over-engineer

- Không thêm hạ tầng (Kafka, K8s, auth phức tạp, multi-tenant…) khi phase hiện tại chưa cần.
- Chỉ dựng đủ để chứng minh bài học / giải quyết vấn đề thật của phase đó.

---

## 4. Quy trình cho mỗi ticket

1. **Read** — đọc ticket trong `Backlog.md` + phần liên quan trong `architecture.md`.
2. **Q&A** — ticket có mục **Q&A**: các câu hỏi không suy ra được từ doc/code, user **trả lời trước**
   khi build. Chưa trả lời → **không bắt đầu**. Câu hỏi nảy sinh khi ĐANG làm (không nghĩ ra lúc plan)
   mới được hỏi giữa chừng.
3. **Plan** — tóm tắt cách hiểu, list bước, nêu **giả định**. Mơ hồ ảnh hưởng design → **hỏi, không đoán**.
4. **Build** — code theo convention §6. Đụng dữ liệu gửi ra LLM → áp redaction PII (§9.5).
5. **Verify** — chạy test / uvicorn / curl / `npm run build` thật. **Dán kết quả thật**, không nói suông.
6. **Document** — update `Backlog.md` (status + Kết quả verify + Learning note); update
   `architecture.md` nếu design đổi; ghi tech debt §7 nếu có.
7. **Close + Git** — commit → push → MR → merge (squash) nếu đủ điều kiện (**CI có sẵn nhưng TẮT** (`CI_ENABLED`) ⇒ chưa có bước chờ pipeline).
   Vòng đời này nằm trong `/run-ticket.md` (đã gộp `close-ticket`).
8. **Report** — summary ngắn: đã làm gì, file nào, lệnh verify, link MR, phần chưa làm / tech debt.

---

## 5. Definition of Ready / Definition of Done

**Definition of Ready (DoR)** — ticket chỉ bắt đầu khi có đủ:

- [ ] Bối cảnh & mục tiêu (why) rõ
- [ ] Scope rõ: in / out
- [ ] Acceptance Criteria dạng checklist, verify được
- [ ] Phụ thuộc: ticket nào phải xong trước
- [ ] Ghi chú kỹ thuật: pattern + trade-off chấp nhận

**Definition of Done (DoD):**

- [ ] Code chạy được, pass lint + format
- [ ] Có test tự động (unit bắt buộc; integration nếu có I/O)
- [ ] Đã verify bằng lệnh thật và ghi lại kết quả trong ticket
- [ ] Không hard-code secret / connection string; config qua env
- [ ] **Không rò PII/secret** ra LLM/log/commit (§9.5)
- [ ] `Backlog.md` đã update status + learning note
- [ ] Doc/README liên quan đã update nếu cách chạy thay đổi

**Definition of Done của một PHASE:**

- [ ] Tất cả ticket của phase `Done`
- [ ] Ghi `docs/phases/phase-N.md` (có gì · cách chạy ở thời điểm đó · cái gì chưa có · bài học)
- [ ] Rà tech debt §7: món nào tới điều kiện revisit → tạo ticket phase kế
- [ ] `architecture.md` đánh dấu phase đã xong (nếu roadmap đổi)

---

## 6. Convention code

### Môi trường dev — WSL2 (Ubuntu) — KB-7.1

Mọi thứ dev chạy trong **WSL2 Ubuntu**; Windows chỉ giữ **VS Code (+ Remote-WSL)** và tool phụ (không bắt buộc).
Code **phải** nằm trên Linux FS (`~/projects/kb-khoa-hoc`), **không** dùng `/mnt/c|/mnt/d` (chậm với
`node_modules`/`torch`).

| Thành phần | Cài trong WSL | Version hiện tại |
|---|---|---|
| Python | `uv python install 3.13` → `uv venv --python 3.13 .venv` | 3.13.18 |
| Node | `fnm install --lts` (fnm ở `~/.local/share/fnm`) | 26.13.0 · npm 11.20 |
| Docker | engine dùng cho `docker build` (xem TD-9 về nơi chạy engine) | 29.9.2 |
| GitLab CLI | `glab auth login --hostname gitlab.com --token <PAT>` (PAT scope `api`) | 1.128.0 |
| SSH GitLab | `~/.ssh/id_ed25519` — public key đã add vào GitLab | — |

Lệnh nhanh:

```bash
# BE — test
cd ~/projects/kb-khoa-hoc/Knowledge-base && .venv/bin/python -m pytest -q   # 19 passed
# FE — build
cd ~/projects/kb-khoa-hoc/Knowledge-base-fe && npm ci && npm run build
# Docker
docker build -t kb-be:local .          # trong Knowledge-base/
```

- **EOL**: mỗi repo có `.gitattributes` (`* text=auto eol=lf`) + `core.autocrlf=input` toàn cục → tránh
  churn CRLF khi file đi qua Windows (nguyên nhân 2 repo "dirty toàn bộ" ngay sau khi copy sang WSL).
- Ưu tiên tool **user-space** (`uv`, `fnm`) → không cần `sudo apt` cho Python/Node.

### Backend (`Knowledge-base/`)

- **Language**: Python 3.13. Virtualenv `.venv`. Deps trong `requirements.txt` (range pin).
- **Config**: 12-factor — đọc từ env (`app/core/config.py`). `.env.example` commit; `.env` **không** commit.
- **Layer**: `app/main.py` (routes) → `app/services/*` (business) → `app/models/schemas.py` (pydantic).
  `app/core/config.py` chỉ chứa settings.
- **Async**: endpoint `async`; việc nặng CPU (embedding) đẩy `run_in_executor`.
- **LLM**: dùng `ChatOpenAI` (OpenAI-compatible) → đổi provider chỉ qua env, không sửa logic.
- **Log**: không log PII/secret thô; dùng `logging`, không `print` trong code chạy thật (startup có thể `print`).
- **Test**: `pytest`, đặt trong `tests/`. Dữ liệu test là **giả** (`user@example.com`).

### Frontend (`Knowledge-base-fe/`)

- **Framework**: Next.js 16 (App Router) · React 19 · TypeScript · Tailwind v4 · Radix/shadcn.
- **Component**: đặt trong `components/`; UI primitives (`components/ui/`) theo shadcn. Dùng `clsx` + `tailwind-merge`.
- **API**: gọi backend qua `NEXT_PUBLIC_API_PROXY_URL` (mặc định `http://localhost:8000`), endpoint `/chat`.
- **State/validate**: `react-hook-form` + `zod` khi có form.
- **Không hardcode** URL/key; dùng env `NEXT_PUBLIC_*`.
- **Style**: theo convention hiện có trong `app/page.tsx`; không thêm lib UI mới khi chưa cần (hỏi trước).
- **Vòng lặp sửa UI (KB-4.9)**: dùng `npm run dev` (:3000) + `npm run test:e2e` (Playwright, tự bật dev server) — ~1–3s/vòng.
  `docker compose up -d --build chatbot-ui` (~60–90s) **chỉ** khi cần production/Docker parity (build-time `NEXT_PUBLIC_*`,
  healthcheck, image) hoệc một lần cuối ticket (`npm run test:e2e:prod`).

### Git (chung)

- **Commit**: Conventional Commits — `feat|fix|docs|refactor|test|chore(scope): mô tả`, nhắc ticket ID.
- **Branch**: `<type>/<ticket-id>-slug` — vd `feat/kb-1.1-pii-redaction`.
- **GitHub Flow**: `main` luôn chạy được; nhánh ngắn hạn + **MR**; **commit + đóng ticket sau mỗi ticket**.
- **CI có sẵn nhưng TẮT mặc định** (KB-5.7): 2 repo có `.gitlab-ci.yml` với gate `CI_ENABLED` (chưa đặt biến ⇒ **không** tạo pipeline) ⇒ điều kiện merge vẫn là ticket Done + MR có summary + không conflict. Khi bật `CI_ENABLED=true` → thêm điều kiện **pipeline xanh** vào `/run-ticket.md`.
- Chi tiết + cách tạo/merge MR: `.clinerules/10-git-workflow.md` và `/run-ticket.md`.

---

## 7. Convention ticket trong `Backlog.md`

- **ID**: `KB-<phase>.<số>` — ví dụ `KB-0.1`, `KB-1.3`. Không đổi ID sau khi tạo.
- **Trạng thái**: `Todo` → `In Progress` → `Review` → `Done` (hoặc `Blocked` + lý do).
- **Ước lượng**: `S` (< nửa ngày) / `M` (1–2 ngày) / `L` (3–5 ngày). Nếu `L` → **phải tách nhỏ**.
- **Repo**: ghi rõ `BE` / `FE` / `BE+FE`.
- Viết như **BA đã define xong**: mô tả được, verify được, không mơ hồ.
- Mỗi ticket: Bối cảnh → Mục tiêu → In scope → Out of scope → Acceptance Criteria → **Q&A (user trả lời
  trước khi làm)** → Ghi chú kỹ thuật → Kết quả verify → Learning note. Phase xa chỉ để mức **epic**.

---

## 8. AI agent — cách trả lời

- Trả lời **tiếng Việt**, giữ keyword tiếng Anh. Không lặp lại yêu cầu của user.
- Ngắn gọn, ưu tiên bullet / bảng. Không lan man.
- Luôn nêu **giả định** khi thiếu thông tin, thay vì im lặng chọn bừa.
- Có nhiều phương án → so sánh bằng bảng **Ưu / Nhược / Khi nào dùng**, rồi mới recommend.
- **Không bịa**: không bịa API, version, benchmark. Không claim "đã test" khi chưa chạy.
- Khi sửa nhiều file → list rõ file nào, sửa gì, vì sao.
- Cuối mỗi task → tóm tắt + lệnh để user tự verify.

---

## 9. Những việc KHÔNG được làm

- ❌ Build một loạt feature trong 1 lượt
- ❌ Thêm hạ tầng/công nghệ ngoài scope của phase hiện tại
- ❌ Đổi kiến trúc/LLM provider mà không update `architecture.md` + viết ADR
- ❌ Commit secret, token, connection string thật, hoặc PII
- ❌ Đánh dấu ticket `Done` khi chưa chạy verify thật
- ❌ Merge PR khi chưa verify hoặc chưa có tóm tắt
- ❌ Viết doc dài dòng, không có ví dụ / số liệu cụ thể
- ❌ Tự ý đổi scope ticket đang làm — có gì mới thì tạo ticket mới

---

## 9.5. PII & secret safety (README kỹ thuật ở `.clinerules/30-pii-safety.md`)

Đây là **knowledge base cá nhân** → tài liệu có thể chứa PII/secret, mà LLM là **bên thứ ba**.

- Ranh giới: **PII** (email cá nhân, sđt, CCCD, số TK, địa chỉ, ngày sinh) và **secret**
  (mật khẩu, `sk-…`, `gsk_…`, JWT, private key, connection string) → **phải che trước khi gửi LLM**.
- Mọi request ra LLM đi qua `app/services/pii_service.py` (`PIIRedactor`). Mặc định **BẬT**.
- Không log/echo PII thô. Example trong doc/test dùng dữ liệu giả.
- Nghi lộ secret → **rotate ngay** (xoá commit là chưa đủ).
- Chi tiết: rule `30-pii-safety.md`, skill `kb-pii-redaction`, tool `tools/pii_scan.py`.

---

## 10. AI assets (rules / skills / workflows / tools)

Bộ công cụ giúp Cline làm việc nhất quán, tiết kiệm token. **File này vẫn là nguồn sự thật.**

| Loại | Vị trí | Vai trò |
|---|---|---|
| Rule | `AGENTS.md` | Working agreement — luôn active |
| Rule | `.clinerules/00-context.md` | Nạp context (Memory Bank lite) |
| Rule | `.clinerules/10-git-workflow.md` | Git workflow: commit sau mỗi ticket, nhánh, PR |
| Rule | `.clinerules/20-tech-debt.md` | Ghi tech debt vào `Backlog.md` §7 |
| Rule | `.clinerules/30-pii-safety.md` | Che PII/secret trước khi gửi LLM / commit |
| Skill | `.cline/skills/kb-ticket` | Format ticket BA-style + DoR/DoD |
| Skill | `.cline/skills/kb-verify` | Verify bằng lệnh thật + dán output |
| Skill | `.cline/skills/kb-adr` | Cách viết ADR |
| Skill | `.cline/skills/kb-pii-redaction` | Triển khai/verify redaction PII |
| Workflow | `.clinerules/workflows/run-ticket.md` | `/run-ticket.md` — thực thi **+ đóng** 1 ticket (gồm git: commit→push→MR→merge) |
| Workflow | `.clinerules/workflows/new-ticket.md` | `/new-ticket.md` — breakdown epic + **Q&A planning** |
| Tool | `tools/pii_scan.py` | Quét PII/secret trong file |
| Tool | `tools/verify.sh` | Gom lệnh verify BE + FE |
| Tool | `tools/setup-wsl-docker-engine.sh` | Cài **docker engine native trong WSL** (bỏ Docker Desktop integration) — KB-7.1 |
| Tool | `Knowledge-base-fe/tools/setup-playwright.sh` | Cài **Playwright + Chromium không cần sudo** (tải `.deb` X11 rồi `dpkg -x`) — KB-4.9 |
| Test | `Knowledge-base-fe/e2e/ui.spec.ts` | **Playwright e2e** trên Chromium thật: 7 check (shell, 720px, theme, persist, Sheet focus/ESC, ồn nguồn không tràn, 1900px) + ảnh chụp — `npm run test:e2e` |
| Doc | `docs/adr/` | **17 ADR** (0001→0017) + [`README.md`](docs/adr/README.md) làm **lộ trình đọc** + 28 câu ôn tập — đọc "vì sao" trước khi sửa code |

Quy ước:

- **Rule** = behavioral, luôn active. **Skill** = kiến thức load on-demand. **Workflow** = quy trình
  nhiều bước, gọi bằng `/filename.md`.
- **Memory Bank lite**: dùng `architecture.md` + `Backlog.md`, không tạo `memory-bank/` riêng.
- `.cline/` và `.clinerules/` được commit vào repo nhưng **không** chứa secret/API key.
- Thêm skill mới đặt tên `kb-*`; thêm workflow đặt tên `<verb>-<object>.md` — nhớ update bảng trên.
