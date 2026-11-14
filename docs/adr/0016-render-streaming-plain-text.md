# ADR-0016 — Render khi stream: plain text, markdown parse **1 lần** khi `end`

| | |
|---|---|
| **Trạng thái** | Accepted (backfill 2026-11-10) · TD-21/TD-22 đã trả |
| **Ngày** | 2026-11-09 |
| **Liên quan** | KB-5.6 (trả TD-21, TD-22), KB-4.11 (pha truy hồi), ADR-0009 (SSE) · `architecture.md` §5 · code: `components/message-with-citations.tsx`, `components/chat-messages.tsx`, test: `tests/stream-render.test.tsx` |

## Context

Khi stream, mỗi token là 1 lần state đổi. Bản đầu render **markdown đầy đủ** cho mỗi lần ⇒ với câu 300
token, markdown parser chạy **300 lần** trên chuỗi ngày càng dài: chi phí O(n²) và UI giật trên máy yếu.
Đo được: 300 lần parse markdown/câu; message cũ bị parse lại 40 lần do re-render cha.

## Options

| Phương án | Ưu | Nhược | Khi nào dùng |
|---|---|---|---|
| **Plain text khi stream + parse markdown 1 lần khi `end`** (chọn) | 0 parse trong lúc stream; UI mượt; code đơn giản | trong lúc stream **không** thấy bold/code/heading (trade-off có chủ ý) | ⭐ Câu trả lời dài, stream |
| Render markdown mỗi token (bản cũ) | đẹp ngay từ đầu | 300 lần parse/câu, giật, tốn CPU client | Câu rất ngắn |
| Virtualize list + memo hoá markdown | giữ markdown realtime, giảm re-render | thêm dependency, phức tạp, vẫn parse mỗi token | Danh sách rất dài |
| Chỉ append text vào DOM (không React state) | nhanh nhất | đi ngược mô hình React, khó test, khó style | Cần tối ưu cực đoan |

## Decision

1. Trong lúc stream: render **plain text** (`whitespace-pre-wrap`, không parser).
2. Khi nhận event `end`: parse markdown **1 lần** cho message đó, rồi giữ nguyên (memo theo `content` +
   `isStreaming`).
3. Message cũ (đã `end`) **không** re-render khi message mới đang stream (`React.memo` + so sánh props).
4. Bỏ hẳn nhánh render `sources`/`citations` chết trong `MessageWithCitations` (TD-22) và xoá
   `lib/export-utils.ts` không dùng.

## Bằng chứng (số đo thật)

| Chỉ số | Trước KB-5.6 | Sau KB-5.6 | Nguồn |
|---|---|---|---|
| Lần parse markdown / câu 300 token | **300** | **0** khi stream, **1** khi `end` | `tests/stream-render.test.tsx` (mock đếm) |
| Re-render message **cũ** | **40** | **0** | cùng test (đếm render `MarkdownMessage`) |
| Dòng code `MessageWithCitations` | 178 | **72** | KB-5.6 diff |
| Nhánh render chết (`sources`/`citations`) | có | xoá | TD-22 |

## Anti-pattern (làm khác đi thì hỏng ở đâu)

- **Parse markdown mỗi token**: đẹp nhưng O(n²); máy yếu thấy rõ giật sau ~150 token.
- **Không memo message cũ**: mỗi token làm **mọi** message parse lại ⇒ 40 lần/message cũ (đo được).
- **Đổi sang markdown ngay khi `end` mà không giữ chiều cao**: bubble nhảy (layout shift) ⇒ cần style ổn
  định (đã xử lý bằng container không đổi padding, xem e2e "không tràn ngang").
- **Hiện spinner/khung markdown rỗng khi chưa có token**: user tưởng lỗi ⇒ KB-4.11 thêm event `phase` để
  hiện "Đang truy hồi tài liệu".

## Consequences

- **Được**: stream mượt; ít CPU client; test đo được bằng cách mock `MarkdownMessage` và **đếm** số lần
  parse (không phải cảm nhận).
- **Mất**: trong lúc stream text **chưa format** (không bold/code block) — trade-off có chủ ý, chấp nhận vì
  câu trả lời thường < 10 s.
- **Tech debt**: chưa có test cho "layout shift khi chuyển plain → markdown" (chỉ có e2e chụp ảnh).

## Nếu làm lại thì khác gì

1. Ngay từ đầu tách `StreamingText` (plain) và `MarkdownMessage` (parsed) — bản cũ trộn 2 nhánh trong 1
   component 178 dòng, khó thấy chỗ đắt.
2. Thêm **assert chiều cao ổn định** trong e2e (đo `boundingBox` trước/sau `end`) thay vì chỉ chụp ảnh.
3. Cân nhắc render **partial markdown** (chỉ heading/bold, không code block) nếu user phàn nàn text thô.

## Revisit

Xem lại khi:

- Câu trả lời thường **> 2.000 token** (stream thô lâu, user khó đọc) ⇒ partial markdown.
- Danh sách hội thoại **> 200 message** ⇒ cần virtualize (lúc đó mới đáng thêm dependency).
- Có yêu cầu hiển thị công thức/bảng lớn ngay khi stream (KaTeX).
