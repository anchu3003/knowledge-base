/**
 * Test module ghép lịch sử server ↔ local (KB-5.2). Thuần dữ liệu — không render, không network.
 */

import {describe, expect, it} from 'vitest';

import type {ChatSessionRecord} from '@/lib/chat-store';
import {mergeServerConversations, sessionMessagesFromDetail, toChatMessage} from '@/lib/conversations';
import type {ConversationDetail, ConversationSummary} from '@/lib/types';

function localSession(overrides: Partial<ChatSessionRecord> = {}): ChatSessionRecord {
    return {
        id: 'session_local_1',
        title: 'Cuộc trò chuyện cũ',
        createdAt: '2026-01-01T00:00:00.000Z',
        messageCount: 2,
        conversationId: 'conv-1',
        messages: [
            {id: 'u1', role: 'user', content: 'câu hỏi cũ'},
            {id: 'a1', role: 'assistant', content: 'trả lời cũ'},
        ],
        ...overrides,
    };
}

function summary(overrides: Partial<ConversationSummary> = {}): ConversationSummary {
    return {
        id: 'conv-1',
        title: 'Kafka là gì?',
        created_at: '2026-01-02T10:00:00',
        updated_at: '2026-01-02T10:05:00',
        message_count: 2,
        ...overrides,
    };
}

describe('toChatMessage', () => {
    it('map role user và sinh id ổn định theo index', () => {
        const message = toChatMessage({role: 'user', content: 'hỏi', timestamp: 't'}, 0, 's1');

        expect(message).toEqual({id: 's1-srv-0', role: 'user', content: 'hỏi'});
    });

    it('role lạ quy về assistant (không làm vỡ UI)', () => {
        expect(toChatMessage({role: 'system', content: 'x', timestamp: 't'}, 1, 's1').role).toBe('assistant');
    });

    it('lượt bị ngắt giữa stream được đánh dấu stopped', () => {
        const message = toChatMessage(
            {role: 'assistant', content: 'dở', timestamp: 't', interrupted: true},
            2,
            's1',
        );

        expect(message.stopped).toBe(true);
    });
});

describe('sessionMessagesFromDetail', () => {
    it('map toàn bộ messages của detail', () => {
        const detail: ConversationDetail = {
            id: 'conv-1',
            title: 'x',
            created_at: '',
            updated_at: '',
            messages: [
                {role: 'user', content: 'a', timestamp: 't1'},
                {role: 'assistant', content: 'b', timestamp: 't2'},
            ],
        };

        const messages = sessionMessagesFromDetail(detail, 's1');

        expect(messages.map((m) => m.id)).toEqual(['s1-srv-0', 's1-srv-1']);
        expect(messages.map((m) => m.role)).toEqual(['user', 'assistant']);
    });
});

describe('mergeServerConversations', () => {
    it('session có ở cả 2 phía ⇒ giữ id local, lấy title của server', () => {
        const merged = mergeServerConversations([summary()], [localSession()]);

        expect(merged).toHaveLength(1);
        expect(merged[0].id).toBe('session_local_1');
        expect(merged[0].title).toBe('Kafka là gì?');
        expect(merged[0].messages).toHaveLength(2); // không mất messages đang hiện
    });

    it('session chỉ có trên server ⇒ tạo record mới, messages rỗng (nạp lazy)', () => {
        const merged = mergeServerConversations([summary({id: 'conv-9', title: ''})], []);

        expect(merged).toHaveLength(1);
        expect(merged[0].id).toBe('srv_conv-9');
        expect(merged[0].conversationId).toBe('conv-9');
        expect(merged[0].title).toBe('Hội thoại đã lưu'); // fallback khi server không có title
        expect(merged[0].messages).toEqual([]);
    });

    it('session chỉ có ở local (tạo lúc BE tắt) ⇒ giữ lại, xếp sau', () => {
        const offline = localSession({id: 'session_offline', conversationId: null, title: 'Offline'});

        const merged = mergeServerConversations([summary()], [offline]);

        expect(merged.map((s) => s.id)).toEqual(['srv_conv-1', 'session_offline']);
    });

    it('created_at lỗi ⇒ dùng epoch, không throw', () => {
        const merged = mergeServerConversations([summary({created_at: 'không-phải-ngày'})], []);

        expect(merged[0].createdAt).toBe(new Date(0).toISOString());
    });

    it('messageCount không nhỏ hơn số message local', () => {
        const merged = mergeServerConversations([summary({message_count: 0})], [localSession()]);

        expect(merged[0].messageCount).toBe(2);
    });

    it('không mutate input', () => {
        const local = localSession();
        const snapshot = JSON.parse(JSON.stringify(local));

        mergeServerConversations([summary()], [local]);

        expect(local).toEqual(snapshot);
    });

    it('không phụ thuộc thứ tự: server trước, local-only sau', () => {
        const merged = mergeServerConversations(
            [summary({id: 'conv-1'}), summary({id: 'conv-2', title: 'Thứ hai'})],
            [localSession({id: 'session_offline', conversationId: 'conv-khac'})],
        );

        expect(merged.map((s) => s.id)).toEqual(['srv_conv-1', 'srv_conv-2', 'session_offline']);
    });
});
