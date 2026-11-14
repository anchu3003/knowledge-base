---
name: kb-adr
description: Viết hoặc cập nhật Architecture Decision Record (ADR) cho dự án Knowledge Base theo template 5 mục (Context / Options / Decision / Consequences / Revisit). Dùng khi chốt quyết định lớn — đổi LLM provider, embedding model, vector store, kiến trúc RAG — hoặc khi tạo/sửa file trong docs/adr/.
---

# Viết ADR cho Knowledge Base

ADR là **bắt buộc** khi thay đổi lớn: đổi LLM provider (vd OpenAI → Groq), đổi embedding model,
đổi vector store (ChromaDB → khác), đổi kiến trúc RAG (`AGENTS.md` §3.3).

## Vị trí & đặt tên

- Thư mục: `docs/adr/`
- Tên file: `NNNN-slug.md`, ví dụ `0001-llm-provider-groq.md`, `0002-embedding-model.md`
- Đánh số tăng dần, không tái sử dụng số đã dùng.

## Template (đúng 5 mục, giữ thứ tự)

```
# ADR-NNNN — <tên quyết định>

| | |
|---|---|
| **Trạng thái** | Proposed / Accepted / Superseded by ADR-XXXX |
| **Ngày** | YYYY-MM-DD |
| **Liên quan** | <ticket / ADR khác> |

## Context
Vấn đề đang gặp, ràng buộc (chi phí, phần cứng local, privacy, tốc độ, quota).

## Options
Bảng so sánh từng phương án: Ưu / Nhược / Khi nào dùng. Nêu cả phương án KHÔNG chọn.

## Decision
Chọn phương án nào, vì sao — đối chiếu Context.

## Consequences
Hệ quả: được gì, mất gì, tech debt phát sinh, ảnh hưởng BE/FE.

## Revisit
Điều kiện cụ thể để xem lại (định lượng được, không ghi "khi cần").
```

## Quality bar

- [ ] Nêu **lý do loại** phương án không chọn.
- [ ] Có bảng trade-off cho từng hạng mục.
- [ ] Mục **Revisit** có điều kiện định lượng được.
- [ ] Nếu quyết định thay `architecture.md` → đã update file đó.
- [ ] **Không** chứa PII/secret thô trong ví dụ.

## Ví dụ Revisit tốt vs kém

| Kém | Tốt |
|---|---|
| "Revisit khi cần" | "Revisit khi vượt 1.000 req/ngày (quota Groq free) hoặc khi cần context > 128K" |
| "Khi hệ thống lớn hơn" | "Khi số doc > 5.000 hoặc retrieval p95 > 1s" |
