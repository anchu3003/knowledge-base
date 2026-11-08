/**
 * Store lịch sử chat ở client (KB-4.9) — Q&A Q3 chốt: **multi-conversation trong `localStorage`**.
 *
 * Vì sao tách thành module (không để trong `page.tsx`):
 * - Logic lưu/đọc + migrate test được bằng vitest, không cần render.
 * - Đọc bằng `useSyncExternalStore` ⇒ `getServerSnapshot` trả store rỗng, nên **SSR và lần render đầu
 *   trên client giống nhau** (không lệch hydration), sau đó React tự re-render với dữ liệu thật.
 * - Ghi `localStorage` được **debounce** (mỗi token stream không tạo 1 lần ghi đồng bộ).
 *
 * Giới hạn có chủ ý: chỉ giữ `MAX_SESSIONS` session gần nhất để không phình quota (~5MB).
 */

import type {ChatMessage} from '@/lib/types';

/** Key `localStorage` mới — thay `kb.conversation_id` toàn cục (bản KB-4.1). */
export const CHAT_STORE_KEY = 'kb.chat_sessions';
/** Key cũ chỉ lưu 1 `conversation_id` — đọc 1 lần để migrate. */
export const LEGACY_CONVERSATION_KEY = 'kb.conversation_id';
export const MAX_SESSIONS = 50;
const STORE_VERSION = 1;
/** Gộp các lần ghi liên tiếp (stream token) thành 1 lần ghi. */
const PERSIST_DEBOUNCE_MS = 300;

export interface ChatSessionRecord {
    id: string;
    title: string;
    /** ISO string — `Date` không serialize được ổn định qua JSON. */
    createdAt: string;
    messageCount: number;
    /** `conversation_id` của BE, **riêng cho từng session** (trước đây là 1 key toàn cục). */
    conversationId: string | null;
    messages: ChatMessage[];
}

export interface ChatStoreSnapshot {
    version: number;
    currentSessionId: string | null;
    sessions: ChatSessionRecord[];
}

/** Snapshot rỗng — dùng cho SSR và ref ổn định để `useSyncExternalStore` không loop. */
const EMPTY_STORE: ChatStoreSnapshot = {version: STORE_VERSION, currentSessionId: null, sessions: []};

let memory: ChatStoreSnapshot | null = null;
const listeners = new Set<() => void>();
let persistTimer: ReturnType<typeof setTimeout> | null = null;

function isMessage(value: unknown): value is ChatMessage {
    if (!value || typeof value !== 'object') return false;
    const message = value as Partial<ChatMessage>;
    return (
        typeof message.id === 'string' &&
        (message.role === 'user' || message.role === 'assistant') &&
        typeof message.content === 'string'
    );
}

function isSession(value: unknown): value is ChatSessionRecord {
    if (!value || typeof value !== 'object') return false;
    const session = value as Partial<ChatSessionRecord>;
    return (
        typeof session.id === 'string' &&
        typeof session.title === 'string' &&
        Array.isArray(session.messages) &&
        session.messages.every(isMessage)
    );
}

/**
 * Parse JSON đã lưu. Dữ liệu hỏng/bị sửa tay ⇒ store rỗng, **không throw** (chat không được chết vì storage).
 * Session thiếu field phụ (`conversationId`, `messageCount`) được điền mặc định.
 */
export function parseChatStore(raw: string | null): ChatStoreSnapshot {
    if (!raw) return EMPTY_STORE;
    try {
        const parsed = JSON.parse(raw) as Partial<ChatStoreSnapshot> | null;
        if (!parsed || !Array.isArray(parsed.sessions)) return EMPTY_STORE;

        const sessions = parsed.sessions.filter(isSession).map((session) => ({
            ...session,
            createdAt: typeof session.createdAt === 'string' ? session.createdAt : new Date(0).toISOString(),
            messageCount: session.messages.length,
            conversationId: typeof session.conversationId === 'string' ? session.conversationId : null,
        }));

        if (sessions.length === 0) return EMPTY_STORE;

        const currentSessionId =
            typeof parsed.currentSessionId === 'string' && sessions.some((s) => s.id === parsed.currentSessionId)
                ? parsed.currentSessionId
                : sessions[0].id;

        return {version: STORE_VERSION, currentSessionId, sessions: sessions.slice(0, MAX_SESSIONS)};
    } catch {
        return EMPTY_STORE;
    }
}

export function serializeChatStore(store: ChatStoreSnapshot): string {
    return JSON.stringify({...store, sessions: store.sessions.slice(0, MAX_SESSIONS)});
}

/** Tiêu đề session lấy từ câu hỏi đầu tiên của user (cắt 60 ký tự) — trước đây là "New Chat" giả. */
export function deriveTitle(messages: ChatMessage[]): string {
    const firstUser = messages.find((message) => message.role === 'user' && message.content.trim().length > 0);
    if (!firstUser) return 'Cuộc trò chuyện mới';
    const text = firstUser.content.trim().replace(/\s+/g, ' ');
    return text.length > 60 ? `${text.slice(0, 57)}...` : text;
}


// ------------------------------
// Store plumbing (dùng cho `useSyncExternalStore`)
// ------------------------------

function loadFromStorage(storage: Storage): ChatStoreSnapshot {
    const stored = parseChatStore(storage.getItem(CHAT_STORE_KEY));
    if (stored.sessions.length > 0) return stored;

    // Migrate bản KB-4.1: chỉ có 1 `conversation_id` toàn cục, không có messages ⇒ tạo session mang id đó
    const legacy = storage.getItem(LEGACY_CONVERSATION_KEY);
    if (!legacy) return EMPTY_STORE;

    return {
        version: STORE_VERSION,
        currentSessionId: 'session_migrated',
        sessions: [
            {
                id: 'session_migrated',
                title: 'Cuộc trò chuyện cũ',
                createdAt: new Date(0).toISOString(),
                messageCount: 0,
                conversationId: legacy,
                messages: [],
            },
        ],
    };
}

function persistNow() {
    if (typeof window === 'undefined' || !memory) return;
    try {
        window.localStorage.setItem(CHAT_STORE_KEY, serializeChatStore(memory));
    } catch {
        // quota đầy / private mode — bỏ qua, session hiện tại vẫn dùng được trong RAM
    }
}

function schedulePersist() {
    if (persistTimer) return;
    persistTimer = setTimeout(() => {
        persistTimer = null;
        persistNow();
    }, PERSIST_DEBOUNCE_MS);
}

/** Snapshot phía server: **luôn rỗng** ⇒ HTML SSR khớp lần render đầu trên client (không lệch hydration). */
export function getChatStoreServerSnapshot(): ChatStoreSnapshot {
    return EMPTY_STORE;
}

/** Snapshot client: nạp lazy 1 lần rồi cache; ref chỉ đổi khi `setChatStore` được gọi. */
export function getChatStoreSnapshot(): ChatStoreSnapshot {
    if (typeof window === 'undefined') return EMPTY_STORE;
    if (!memory) memory = loadFromStorage(window.localStorage);
    return memory;
}

export function subscribeChatStore(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
}

export type ChatStoreUpdater = (previous: ChatStoreSnapshot) => ChatStoreSnapshot;

/** Cập nhật store: ghi RAM + notify ngay (UI mượt), `localStorage` thì debounce. */
export function setChatStore(updater: ChatStoreUpdater): ChatStoreSnapshot {
    const previous = getChatStoreSnapshot();
    const next = updater(previous);

    const capped: ChatStoreSnapshot =
        next.sessions.length > MAX_SESSIONS ? {...next, sessions: next.sessions.slice(0, MAX_SESSIONS)} : next;

    memory = capped;
    schedulePersist();
    listeners.forEach((listener) => listener());
    return capped;
}

/** Xoá sạch (test hoặc nút "xoá lịch sử" sau này). */
export function clearChatStore(): void {
    memory = EMPTY_STORE;
    if (typeof window !== 'undefined') {
        try {
            window.localStorage.removeItem(CHAT_STORE_KEY);
        } catch {
            // bỏ qua
        }
    }
    listeners.forEach((listener) => listener());
}

/** Chỉ dùng trong test: reset cache trong RAM (không đụng localStorage). */
export function resetChatStoreCache(): void {
    memory = null;
    if (persistTimer) {
        clearTimeout(persistTimer);
        persistTimer = null;
    }
}
