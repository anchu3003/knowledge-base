/**
 * Map dữ liệu lịch sử hội thoại từ server sang store của FE (KB-5.2).
 *
 * Quy ước Q&A KB-5.2 Q2: **server là nguồn sự thật**, `localStorage` chỉ là cache/fallback.
 * Vì vậy ở đây chỉ *ghép* danh sách server vào danh sách local (thay vì giải quyết xung đột 2 chiều):
 * - Session có trên server **và** local ⇒ giữ `id` local (để `currentSessionId` không nhảy), lấy
 *   `title`/`createdAt` của server khi có.
 * - Session chỉ có trên server ⇒ tạo record mới, messages nạp lazy bằng `GET /conversations/{id}`
 *   (xem `sessionMessagesFromDetail`).
 * - Session chỉ có ở local (tạo lúc BE tắt) ⇒ **giữ lại**, không xoá dữ liệu của người dùng.
 *
 * Hàm thuần (không đụng `localStorage`/network) ⇒ test bằng vitest, không cần render.
 */

import {MAX_SESSIONS, type ChatSessionRecord} from './chat-store';
import type {ChatMessage, ConversationDetail, ConversationMessage, ConversationSummary} from './types';

/** Tiền tố id để phân biệt session "chỉ có trên server" với session tạo ở FE. */
export const SERVER_SESSION_PREFIX = 'srv_';

function parseDate(value: string | undefined, fallback: string): string {
    if (!value) return fallback;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? fallback : date.toISOString();
}

/** Chuyển 1 message của server sang `ChatMessage` của FE (id tổng hợp, ổn định theo index). */
export function toChatMessage(
    message: ConversationMessage,
    index: number,
    sessionId: string,
): ChatMessage {
    const role = message.role === 'user' ? 'user' : 'assistant';
    const converted: ChatMessage = {
        id: `${sessionId}-srv-${index}`,
        role,
        content: message.content,
    };
    if (message.interrupted) {
        // Lượt trả lời bị ngắt giữa stream (KB-3.3) — giữ dấu để UI không hiểu nhầm là câu hoàn chỉnh.
        converted.stopped = true;
    }
    return converted;
}

/** Messages của 1 session, lấy từ `GET /conversations/{id}`. */
export function sessionMessagesFromDetail(
    detail: ConversationDetail,
    sessionId: string,
): ChatMessage[] {
    return detail.messages.map((message, index) => toChatMessage(message, index, sessionId));
}

/**
 * Ghép danh sách conversation của server vào danh sách session đang có ở FE.
 *
 * Không mutate đầu vào; kết quả giới hạn `MAX_SESSIONS`.
 */
export function mergeServerConversations(
    server: ConversationSummary[],
    local: ChatSessionRecord[],
): ChatSessionRecord[] {
    const epoch = new Date(0).toISOString();
    const localByConversationId = new Map<string, ChatSessionRecord>();
    for (const session of local) {
        if (session.conversationId) localByConversationId.set(session.conversationId, session);
    }

    const serverIds = new Set(server.map((item) => item.id));
    const merged: ChatSessionRecord[] = server.map((item) => {
        const existing = localByConversationId.get(item.id);
        const createdAt = parseDate(item.created_at, existing?.createdAt ?? epoch);

        if (existing) {
            return {
                ...existing,
                // Server có tiêu đề ⇒ dùng; không có ⇒ giữ tiêu đề local (đã derive từ câu hỏi đầu).
                title: item.title || existing.title,
                createdAt,
                messageCount: Math.max(existing.messages.filter((m) => !m.isStreaming).length, item.message_count),
            };
        }

        return {
            id: `${SERVER_SESSION_PREFIX}${item.id}`,
            title: item.title || 'Hội thoại đã lưu',
            createdAt,
            messageCount: item.message_count,
            conversationId: item.id,
            // Nạp lazy: list endpoint không trả messages (giữ payload nhỏ).
            messages: [],
        };
    });

    const localOnly = local.filter(
        (session) => !session.conversationId || !serverIds.has(session.conversationId),
    );

    return [...merged, ...localOnly].slice(0, MAX_SESSIONS);
}
