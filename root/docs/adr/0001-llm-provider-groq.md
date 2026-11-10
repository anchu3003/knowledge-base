# ADR-0001 — Chọn LLM provider: Groq (free tier)

| | |
|---|---|
| **Trạng thái** | Accepted |
| **Ngày** | 2026-11-07 |
| **Liên quan** | KB-0.2, KB-0.4 |

## Context

Backend dùng `ChatOpenAI` (LangChain) → gọi được mọi endpoint **OpenAI-compatible**.
Trước đây trỏ vào endpoint của trường (`aiportalapi.stu-platform.live`) và hard-code trong
`get_settings()` — không linh hoạt, phụ thuộc bên thứ ba.

Mục tiêu mới: dùng **free tier** cho một knowledge base cá nhân, chi phí ~0.

Ràng buộc:

- Máy local: i5-12600K · 32GB RAM · **GTX 1050 Ti 4GB VRAM** → chạy LLM local chỉ được model nhỏ (3B),
  chất lượng thấp cho tài liệu kỹ thuật → **không dùng local làm chính**.
- Embeddings đã chạy **local** (miễn phí) → chỉ cần API cho phần sinh câu trả lời.
- Ưu tiên **privacy**: nội dung gửi lên provider nên hạn chế (đã có KB-1.1 che PII).

## Options

| Provider | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Groq** | Rất nhanh; model mạnh (`gpt-oss-120b`); free tier rõ ràng; không cần thẻ | Cần internet; quota 1K req/ngày; dữ liệu qua cloud | ⭐ Dùng chính |
| Google Gemini (AI Studio) | Quota rộng, chất lượng cao | Free tier **có thể dùng nội dung để cải thiện sản phẩm** → kém private | Backup khi cần context dài |
| OpenRouter `:free` | 1 key nhiều model | Free chỉ 50 req/ngày | Thử nhiều model |
| Ollama (local) | Riêng tư tuyệt đối, không quota | Máy chỉ chạy được model 3B → chất lượng thấp | Khi offline |
| Trường (`aiportal`) | Miễn phí | Phụ thuộc bên thứ ba, không kiểm soát | (bỏ) |

## Decision

Chọn **Groq** làm provider chính:

- `OPENAI_BASE_URL=https://api.groq.com/openai/v1`
- `OPENAI_MODEL=openai/gpt-oss-120b`
- `OPENAI_API_TYPE=openai`

Đồng thời **bỏ hard-code** base URL trong `get_settings()` → provider điều khiển hoàn toàn bằng env.

Lý do loại phương án khác: Gemini free tier đánh đổi privacy (không hợp knowledge base cá nhân có PII);
OpenRouter free quá ít quota; Ollama local không đủ phần cứng; trường là phụ thuộc ngoài tầm kiểm soát.

## Consequences

- **Được**: chi phí ~0; tốc độ tốt; máy local nhẹ tải; đổi provider chỉ bằng env.
- **Mất / rủi ro**: phụ thuộc internet + quota Groq (1K req/ngày, 30 RPM); nội dung gửi lên cloud
  (giảm thiểu bằng redaction PII — KB-1.1).
- **Tech debt**: chưa có retry/backoff cho `429` (đưa vào Phase 3); chưa có fallback provider tự động.

## Revisit

Revisit khi một trong các điều kiện sau đúng:

- Vượt **1.000 req/ngày** hoặc thường xuyên gặp `429` (quota Groq free).
- Cần **context window > 128K** hoặc model mạnh hơn.
- Cần chạy **hoàn toàn offline / riêng tư** (→ Ollama với model vừa máy, hoặc nâng GPU ≥ 12GB VRAM).
