import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {
    CHAT_STORE_KEY,
    LEGACY_CONVERSATION_KEY,
    MAX_SESSIONS,
    clearChatStore,
    deriveTitle,
    getChatStoreServerSnapshot,
    getChatStoreSnapshot,
    parseChatStore,
    resetChatStoreCache,
    serializeChatStore,
    setChatStore,
    subscribeChatStore,
    type ChatSessionRecord,
} from '@/lib/chat-store';

const message = (id: string, role: 'user' | 'assistant', content: string) => ({id, role, content});

const session = (overrides: Partial<ChatSessionRecord> = {}): ChatSessionRecord => ({
    id: 's1',
    title: 'Cuộc trò chuyện mới',
    createdAt: '2026-11-08T00:00:00.000Z',
    messageCount: 0,
    conversationId: null,
    messages: [],
    ...overrides,
});

describe('chat-store — parse/serialize (KB-4.9)', () => {
    it('dữ liệu hỏng hoặc rỗng ⇒ store rỗng, không throw', () => {
        expect(parseChatStore(null).sessions).toEqual([]);
        expect(parseChatStore('not json').sessions).toEqual([]);
        expect(parseChatStore('{"sessions": "nope"}').sessions).toEqual([]);
        expect(parseChatStore('{"sessions": [{"id": 1}]}').sessions).toEqual([]);
    });

    it('bỏ session sai shape, giữ session hợp lệ và tính lại messageCount', () => {
        const raw = JSON.stringify({
            sessions: [
                {...session(), messages: [message('m1', 'user', 'hỏi gì đó')]},
                {id: 'bad', title: 'x'},
            ],
            currentSessionId: 's1',
        });

        const store = parseChatStore(raw);
        expect(store.sessions).toHaveLength(1);
        expect(store.sessions[0].messageCount).toBe(1);
        expect(store.currentSessionId).toBe('s1');
    });

    it('currentSessionId trỏ session không tồn tại ⇒ fallback session đầu', () => {
        const raw = JSON.stringify({sessions: [session({id: 'a'}), session({id: 'b'})], currentSessionId: 'zzz'});
        expect(parseChatStore(raw).currentSessionId).toBe('a');
    });

    it('cắt còn MAX_SESSIONS khi nạp', () => {
        const sessions = Array.from({length: MAX_SESSIONS + 5}, (_, index) => session({id: `s${index}`}));
        const store = parseChatStore(JSON.stringify({sessions, currentSessionId: 's0'}));
        expect(store.sessions).toHaveLength(MAX_SESSIONS);
    });

    it('serialize → parse giữ nguyên số session', () => {
        const store = {version: 1, currentSessionId: 's1', sessions: [session()]};
        expect(parseChatStore(serializeChatStore(store)).sessions[0].id).toBe('s1');
    });
});

describe('chat-store — deriveTitle', () => {
    it('lấy câu hỏi đầu tiên của user, cắt 60 ký tự', () => {
        const long = 'a'.repeat(100);
        expect(deriveTitle([message('g', 'assistant', 'chào'), message('u', 'user', long)])).toBe(`${'a'.repeat(57)}...`);
        expect(deriveTitle([message('u', 'user', '  Docker   là gì  ')])).toBe('Docker là gì');
    });

    it('chưa có câu hỏi ⇒ title mặc định', () => {
        expect(deriveTitle([message('g', 'assistant', 'chào')])).toBe('Cuộc trò chuyện mới');
    });
});

describe('chat-store — đọc/ghi + localStorage (KB-4.9)', () => {
    beforeEach(() => {
        window.localStorage.clear();
        resetChatStoreCache();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('server snapshot luôn rỗng (SSR không lệch hydration)', () => {
        expect(getChatStoreServerSnapshot().sessions).toEqual([]);
    });

    it('setChatStore cập nhật RAM ngay và ghi localStorage sau debounce', () => {
        vi.useFakeTimers();
        setChatStore((previous) => ({...previous, currentSessionId: 's1', sessions: [session()]}));

        expect(getChatStoreSnapshot().currentSessionId).toBe('s1');
        expect(window.localStorage.getItem(CHAT_STORE_KEY)).toBeNull();

        vi.advanceTimersByTime(400);
        expect(JSON.parse(window.localStorage.getItem(CHAT_STORE_KEY)!).sessions).toHaveLength(1);
    });

    it('nạp lại từ localStorage sau khi mount lại (mô phỏng F5)', () => {
        vi.useFakeTimers();
        setChatStore((previous) => ({
            ...previous,
            currentSessionId: 's1',
            sessions: [session({messages: [message('u1', 'user', 'câu hỏi cũ')], messageCount: 1})],
        }));
        vi.advanceTimersByTime(400);

        resetChatStoreCache(); // "reload": RAM mất, localStorage còn
        const restored = getChatStoreSnapshot();
        expect(restored.sessions[0].messages[0].content).toBe('câu hỏi cũ');
        expect(restored.currentSessionId).toBe('s1');
    });

    it('migrate `kb.conversation_id` cũ thành session đầu tiên', () => {
        window.localStorage.setItem(LEGACY_CONVERSATION_KEY, 'conv-old');
        const store = getChatStoreSnapshot();

        expect(store.sessions).toHaveLength(1);
        expect(store.sessions[0].conversationId).toBe('conv-old');
        expect(store.currentSessionId).toBe(store.sessions[0].id);
    });

    it('subscribe được notify mỗi lần setChatStore, unsubscribe thì thôi', () => {
        const listener = vi.fn();
        const unsubscribe = subscribeChatStore(listener);

        setChatStore((previous) => ({...previous, sessions: [session()]}));
        expect(listener).toHaveBeenCalledTimes(1);

        unsubscribe();
        setChatStore((previous) => ({...previous, sessions: []}));
        expect(listener).toHaveBeenCalledTimes(1);
    });

    it('clearChatStore xoá cả RAM và key localStorage', () => {
        setChatStore((previous) => ({...previous, sessions: [session()]}));
        clearChatStore();
        expect(getChatStoreSnapshot().sessions).toEqual([]);
        expect(window.localStorage.getItem(CHAT_STORE_KEY)).toBeNull();
    });
});
