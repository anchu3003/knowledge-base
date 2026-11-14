'use client';

/**
 * Bubble nội dung của một message (KB-4.2 + KB-5.6).
 *
 * Hai thay đổi ở KB-5.6:
 * - **Xoá nhánh render `sources`/`citations`** (~130 dòng): nguồn từ KB-4.3 do `SourcesPanel` lo,
 *   `ChatMessages` không truyền 2 prop này ⇒ code cũ là dead code (TD-22).
 * - **Không parse markdown khi đang stream** (TD-21): `react-markdown` parse lại toàn bộ câu trả lời
 *   ở **mỗi token** ⇒ 300 token = 300 lần parse (đo được ở `tests/stream-render.test.tsx`). Lúc stream
 *   hiển thị **plain text** (`whitespace-pre-wrap`), khi `end` tới mới render markdown đầy đủ ⇒ 1 lần parse.
 *
 * `memo` + callback **ổn định** (`messageId` + `onCitationClick`) ⇒ message đã xong không render lại
 * khi message khác đang stream (đo được: 40 → 0 lần).
 */

import {memo, useCallback} from 'react';

import {MarkdownMessage} from './markdown-message';
import {TypingIndicator} from './typing-indicator';

interface MessageWithCitationsProps {
    content: string;
    isStreaming?: boolean;
    isUser?: boolean;
    /** Id của message — ghép với `citationId` để callback của cha không đổi identity mỗi render. */
    messageId?: string;
    /** Bấm chip `[S#]` trong câu trả lời (KB-4.2; KB-4.3 nối vào panel nguồn). */
    onCitationClick?: (messageId: string, citationId: string) => void;
    /** Người dùng bấm **Stop** giữa lúc stream (KB-4.4) — text đã nhận vẫn giữ, chỉ thêm nhãn. */
    stopped?: boolean;
}

export const MessageWithCitations = memo(function MessageWithCitations({
                                                                          content,
                                                                          isStreaming = false,
                                                                          isUser = false,
                                                                          messageId,
                                                                          onCitationClick,
                                                                          stopped = false,
                                                                      }: MessageWithCitationsProps) {
    const handleCitationClick = useCallback(
        (citationId: string) => {
            if (messageId) onCitationClick?.(messageId, citationId);
        },
        [messageId, onCitationClick],
    );

    return (
        <div className="relative space-y-2">
            {/* KB-4.9: nút "Sao chép" nằm dưới nội dung, chỉ hiện khi hover/focus ⇒ không đè lên chữ */}
            <div>
                {isUser ? (
                    <p className="break-words whitespace-pre-wrap">{content}</p>
                ) : isStreaming ? (
                    // Đang stream: plain text (chưa parse markdown) — nội dung y nguyên, chỉ chưa format.
                    <p className="break-words whitespace-pre-wrap" data-testid="streaming-plaintext">
                        {content}
                    </p>
                ) : (
                    <MarkdownMessage content={content} onCitationClick={handleCitationClick}/>
                )}
                {isStreaming && <TypingIndicator/>}
                {stopped && !isStreaming && (
                    <p className="mt-2 text-xs font-medium text-amber-600 dark:text-amber-400">
                        ⏹ Đã dừng — câu trả lời chỉ gồm phần đã nhận.
                    </p>
                )}
            </div>
        </div>
    );
});
