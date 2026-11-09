'use client';

import {useEffect, useRef, useState, useSyncExternalStore} from 'react';

import {AppHeader} from '@/components/app-header';
import {AppSidebar, SidebarContent, type ChatSession} from '@/components/app-sidebar';
import {ChatComposer} from '@/components/chat-composer';
import {ChatMessages, type CitationFocus} from '@/components/chat-messages';
import {DocumentsPanel} from '@/components/documents-panel';
import {ErrorBanner} from '@/components/error-banner';
import {ScrollArea} from '@/components/ui/scroll-area';
import {
    MAX_SESSIONS,
    deriveTitle,
    getChatStoreServerSnapshot,
    getChatStoreSnapshot,
    setChatStore,
    subscribeChatStore,
    type ChatSessionRecord,
} from '@/lib/chat-store';
import {ApiError, STREAMING_ENABLED, StreamAbortedError, postChat, streamChat} from '@/lib/api';
import {describeApiError, type ApiErrorView} from '@/lib/errors';
import {phaseOf} from '@/lib/stream-phase';
import type {ChatMessage} from '@/lib/types';

/** Default khớp BE (`max_tokens=1000`). */
const DEFAULT_MAX_TOKENS = 1000;
const DEFAULT_TEMPERATURE = 0.7;

const GREETING =
    'Chào bạn! Mình là trợ lý trên kho tài liệu cá nhân của bạn. Hỏi mình bất cứ điều gì về tài liệu đã nạp ' +
    '(ghi chú kỹ thuật, ôn phỏng vấn, tài liệu tiếng Anh…).';

const INITIAL_MESSAGES: ChatMessage[] = [{id: 'greeting', role: 'assistant', content: GREETING}];

let sessionSeq = 0;
let messageSeq = 0;

/**
 * Sinh id message trong **event handler**. Đặt ở module scope để rule `react-hooks/purity` không coi
 * `Date.now()` là impure trong thân component (compiler không phân biệt được handler vs render).
 */
function nowMs(): number {
    return Date.now();
}

function createMessageId(prefix: 'user' | 'assistant'): string {
    messageSeq += 1;
    return `${prefix}-${Date.now()}-${messageSeq}`;
}

/** Tạo session mới — gọi trong **event handler** (không phải render) nên `Date.now()` hợp lệ. */
function buildSession(): ChatSessionRecord {
    sessionSeq += 1;
    return {
        id: `session_${Date.now()}_${sessionSeq}`,
        title: 'Cuộc trò chuyện mới',
        createdAt: new Date().toISOString(),
        messageCount: 0,
        conversationId: null,
        messages: INITIAL_MESSAGES,
    };
}

/**
 * Trang chat (KB-4.8 tách component, KB-4.9 chuyển state lịch sử sang `lib/chat-store.ts`).
 *
 * Lịch sử hội thoại **không** còn là state RAM trong `page.tsx`: nó nằm trong store ngoài React
 * (in-memory + `localStorage`) và đọc bằng `useSyncExternalStore` ⇒ F5 không mất hội thoại, và
 * `getServerSnapshot` rỗng nên SSR không lệch hydration.
 */
export default function ChatPage() {
    const store = useSyncExternalStore(subscribeChatStore, getChatStoreSnapshot, getChatStoreServerSnapshot);

    const activeSession = store.sessions.find((session) => session.id === store.currentSessionId) ?? null;
    const messages = activeSession && activeSession.messages.length > 0 ? activeSession.messages : INITIAL_MESSAGES;
    const conversationId = activeSession?.conversationId ?? null;

    const [input, setInput] = useState('');
    const [maxTokens, setMaxTokens] = useState<number>(DEFAULT_MAX_TOKENS);
    const [temperature, setTemperature] = useState<number>(DEFAULT_TEMPERATURE);
    const [formError, setFormError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    // KB-4.11: pha truy hồi ↔ đang viết + đếm giây đã chờ
    const [requestStartedAt, setRequestStartedAt] = useState<number | null>(null);
    const [streamStarted, setStreamStarted] = useState(false);
    // KB-4.1: lỗi API hiển thị bằng banner (thay vì message giả trong khung chat)
    const [apiError, setApiError] = useState<ApiErrorView | null>(null);
    // Câu hỏi của lần gửi lỗi gần nhất — dùng cho nút "Thử lại" (không nhân đôi message user)
    const [retryText, setRetryText] = useState<string | null>(null);
    // KB-4.3: chip `[S#]` nào vừa được bấm ⇒ panel nguồn của message đó scroll + highlight card
    const [citationFocus, setCitationFocus] = useState<CitationFocus | null>(null);
    // KB-4.5: drawer "Kho tài liệu" (status index + readiness + refresh/clear)
    const [showDocumentsPanel, setShowDocumentsPanel] = useState(false);

    const scrollRef = useRef<HTMLDivElement>(null);
    // KB-4.4: controller của request đang stream — nút Stop gọi `abort()`
    const abortRef = useRef<AbortController | null>(null);

    // Auto-scroll xuống cuối mỗi khi có message mới
    useEffect(() => {
        scrollRef.current?.scrollIntoView({behavior: 'smooth'});
    }, [messages]);


    /** Ghi messages của session đang mở; tự set title theo câu hỏi đầu tiên (KB-4.9). */
    const setMessages = (updater: (previous: ChatMessage[]) => ChatMessage[]) => {
        setChatStore((previous) => {
            const active = previous.sessions.find((session) => session.id === previous.currentSessionId);
            const base = active ?? buildSession();
            const nextMessages = updater(base.messages.length > 0 ? base.messages : INITIAL_MESSAGES);
            const nextSession: ChatSessionRecord = {
                ...base,
                messages: nextMessages,
                messageCount: nextMessages.length,
                title: deriveTitle(nextMessages),
            };
            const sessions = previous.sessions.some((session) => session.id === nextSession.id)
                ? previous.sessions.map((session) => (session.id === nextSession.id ? nextSession : session))
                : [nextSession, ...previous.sessions].slice(0, MAX_SESSIONS);

            return {...previous, currentSessionId: nextSession.id, sessions};
        });
    };

    /** Đảm bảo luôn có session đang mở trước khi ghi (lần đầu vào app chưa có session nào). */
    const ensureActiveSession = () => {
        setChatStore((previous) => {
            if (previous.sessions.some((session) => session.id === previous.currentSessionId)) return previous;
            const created = buildSession();
            return {...previous, currentSessionId: created.id, sessions: [created, ...previous.sessions]};
        });
    };

    /** `conversation_id` giờ thuộc **từng session** (KB-4.9) thay vì 1 key toàn cục. */
    const setConversationId = (id: string | null) => {
        setChatStore((previous) => ({
            ...previous,
            sessions: previous.sessions.map((session) =>
                session.id === previous.currentSessionId ? {...session, conversationId: id} : session,
            ),
        }));
    };

    const handleSendMessage = async () => {
        setFormError(null);
        if (!input.trim()) {
            setFormError('Hãy nhập câu hỏi trước khi gửi.');
            return;
        }

        if (!Number.isFinite(maxTokens) || maxTokens <= 0 || maxTokens > 2000) {
            setFormError('Max tokens phải là số trong khoảng 1–2000.');
            return;
        }

        if (temperature < 0 || temperature > 1) {
            setFormError('Temperature phải trong khoảng 0–1.');
            return;
        }

        const question = input.trim();
        setInput('');
        await submitQuestion(question, {appendUserMessage: true});
    };

    /** Cập nhật một message theo `id` (dùng cho từng token stream — KB-4.4). */
    const updateAssistant = (id: string, updater: (message: ChatMessage) => ChatMessage) => {
        setMessages((previous) => previous.map((message) => (message.id === id ? updater(message) : message)));
    };

    /** Bỏ bubble assistant rỗng (lỗi/Stop trước khi có token nào) — không để khung chat trống trơn. */
    const dropIfEmpty = (id: string) => {
        setMessages((previous) =>
            previous.filter((message) => !(message.id === id && message.content.trim().length === 0)),
        );
    };

    /**
     * Gửi câu hỏi và cập nhật UI.
     *
     * - **Mặc định stream** `POST /chat/stream` (KB-4.4): chữ hiện dần, Stop huỷ request, giữ partial text.
     * - `NEXT_PUBLIC_STREAMING=false` ⇒ quay lại `POST /chat` blocking (hành vi KB-4.1).
     * - `appendUserMessage=false` khi bấm "Thử lại" — message user đã nằm trong khung chat rồi.
     */
    const submitQuestion = async (question: string, options: {appendUserMessage: boolean}) => {
        setApiError(null);
        setIsLoading(true);
        // KB-4.11: mốc thời gian để hiện "đang truy hồi (ns)" trước khi BE gửi event `start`
        setRequestStartedAt(nowMs());
        setStreamStarted(false);
        ensureActiveSession();

        if (options.appendUserMessage) {
            setMessages((previous) => [...previous, {id: createMessageId('user'), role: 'user', content: question}]);
        }
        // ---- Fallback: blocking `/chat` khi NEXT_PUBLIC_STREAMING=false (hành vi KB-4.1) ----
        if (!STREAMING_ENABLED) {
            try {
                const data = await postChat({
                    message: question,
                    conversation_id: conversationId ?? undefined,
                    max_tokens: maxTokens,
                    temperature,
                });

                if (data.conversation_id) {
                    setConversationId(data.conversation_id);
                }

                // KB-4.3: KHÔNG dedup theo `file_path` — mỗi phần tử `sources[]` là 1 chunk có `citation_id` riêng.
                setMessages((prev) => [
                    ...prev,
                    {
                        id: createMessageId('assistant'),
                        role: 'assistant',
                        content: data.response || '',
                        sources: data.sources ?? [],
                        metadata: data.metadata,
                    },
                ]);
                setRetryText(null);
            } catch (error) {
                // Banner lỗi theo `error.code`; KHÔNG chèn message giả vào khung chat
                setApiError(describeApiError(error));
                setRetryText(question);
                if (!(error instanceof ApiError)) {
                    // lỗi runtime ngoài dự kiến — vẫn log để debug, không lộ ra UI
                    console.debug('Unexpected chat error', error);
                }
            } finally {
                setIsLoading(false);
                // KB-4.11: kết thúc lượt ⇒ tắt khối trạng thái
                setRequestStartedAt(null);
                setStreamStarted(false);
            }
            return;
        }


        // ---- Mặc định: streaming SSE `POST /chat/stream` (KB-4.4) ----
        const assistantId = createMessageId('assistant');
        const controller = new AbortController();
        abortRef.current = controller;
        let failed = false;

        // Bubble rỗng + `isStreaming`: chữ sẽ được nối dần theo từng event `token`
        setMessages((prev) => [...prev, {id: assistantId, role: 'assistant', content: '', isStreaming: true}]);

        try {
            await streamChat(
                {
                    message: question,
                    conversation_id: conversationId ?? undefined,
                    max_tokens: maxTokens,
                    temperature,
                },
                {
                    signal: controller.signal,
                    onEvent: (event) => {
                        if (event.type === 'start') {
                            // KB-4.11: BE đã truy hồi xong ⇒ chuyển pha "đang viết"
                            setStreamStarted(true);
                            if (event.conversation_id) setConversationId(event.conversation_id);
                            if (event.metadata) {
                                updateAssistant(assistantId, (message) => ({...message, metadata: event.metadata}));
                            }
                            return;
                        }

                        if (event.type === 'token') {
                            updateAssistant(assistantId, (message) => ({
                                ...message,
                                content: message.content + event.token,
                            }));
                            return;
                        }

                        if (event.type === 'end') {
                            if (event.conversation_id) setConversationId(event.conversation_id);
                            // `end.answer` là bản chốt của BE ⇒ dùng làm nguồn sự thật (không lệch do token rơi)
                            const finalAnswer = (event.answer ?? '').trim();
                            const emptyAnswer = finalAnswer.length === 0;
                            updateAssistant(assistantId, (message) => ({
                                ...message,
                                content: event.answer ?? message.content,
                                sources: event.sources ?? message.sources,
                                metadata: event.metadata ?? message.metadata,
                                isStreaming: false,
                                // KB-4.11: answer rỗng ⇒ hiện giải thích + Thử lại thay vì bubble trống
                                emptyAnswer,
                            }));
                            if (emptyAnswer) {
                                // giữ câu trả lời rỗng có chủ đích (không dropIfEmpty) để user thấy lý do
                                failed = true;
                                setRetryText(question);
                            }
                            return;
                        }

                        // event `error` giữa stream: banner KB-4.1 + GIỮ partial text đã nhận
                        failed = true;
                        updateAssistant(assistantId, (message) => ({...message, isStreaming: false}));
                        dropIfEmpty(assistantId);
                        setApiError(
                            describeApiError(
                                new ApiError({
                                    code: event.error.code,
                                    message: event.error.message,
                                    requestId: event.error.request_id,
                                    status: 0,
                                }),
                            ),
                        );
                        setRetryText(question);
                    },
                },
            );
            if (!failed) setRetryText(null);
        } catch (error) {
            if (error instanceof StreamAbortedError) {
                // Q&A KB-4.4 Q1: bấm Stop ⇒ GIỮ phần đã nhận, đánh dấu "đã dừng" (BE đã lưu partial)
                updateAssistant(assistantId, (message) => ({...message, isStreaming: false, stopped: true}));
                dropIfEmpty(assistantId);
            } else {
                updateAssistant(assistantId, (message) => ({...message, isStreaming: false}));
                dropIfEmpty(assistantId);
                setApiError(describeApiError(error));
                setRetryText(question);
                if (!(error instanceof ApiError)) {
                    console.debug('Unexpected stream error', error);
                }
            }
        } finally {
            abortRef.current = null;
            setIsLoading(false);
            // KB-4.11: kết thúc lượt ⇒ tắt khối trạng thái
            setRequestStartedAt(null);
            setStreamStarted(false);
        }
    };

    /** Nút **Stop** (KB-4.4): huỷ request đang stream — text đã nhận giữ nguyên. */
    const handleStopStreaming = () => {
        abortRef.current?.abort();
    };

    const handleRetry = async () => {
        if (!retryText) return;
        await submitQuestion(retryText, {appendUserMessage: false});
    };

    /**
     * Bấm chip `[S#]` trong câu trả lời (KB-4.2) → panel nguồn scroll + highlight đúng card (KB-4.3).
     * Cần `messageId` vì mỗi câu trả lời có panel riêng; `nonce` để bấm lại cùng chip vẫn highlight lại.
     */
    const handleCitationClick = (messageId: string, citationId: string) => {
        setCitationFocus((previous) => ({messageId, citationId, nonce: (previous?.nonce ?? 0) + 1}));
    };

    // ---- Session actions (KB-4.9: lưu trong `localStorage` qua `chat-store`) ----

    const handleSelectSession = (sessionId: string) => {
        setChatStore((previous) => ({...previous, currentSessionId: sessionId}));
        setApiError(null);
        setRetryText(null);
        setCitationFocus(null);
    };

    const handleNewChat = () => {
        const created = buildSession();
        setChatStore((previous) => ({
            ...previous,
            currentSessionId: created.id,
            sessions: [created, ...previous.sessions].slice(0, MAX_SESSIONS),
        }));
        setApiError(null);
        setRetryText(null);
        setCitationFocus(null);
        setInput('');
    };

    /** Xoá session; xoá session cuối cùng ⇒ tạo session trống mới (không để màn hình không có session). */
    const handleDeleteSession = (sessionId: string) => {
        setChatStore((previous) => {
            const sessions = previous.sessions.filter((session) => session.id !== sessionId);
            if (sessions.length === 0) {
                const created = buildSession();
                return {...previous, currentSessionId: created.id, sessions: [created]};
            }
            const currentSessionId = sessions.some((session) => session.id === previous.currentSessionId)
                ? previous.currentSessionId
                : sessions[0].id;
            return {...previous, currentSessionId, sessions};
        });
    };

    // KB-4.11: pha hiện tại — 'retrieving' (chưa có `start`) → 'writing' (đã có `start`)
    const streamPhase = phaseOf({loading: isLoading, started: streamStarted, finished: false});

    // Model thật BE đã dùng (metadata của câu trả lời gần nhất) — không phải select giả
    const activeModel = [...messages]
        .reverse()
        .find((message) => message.role === 'assistant' && message.metadata?.model)?.metadata?.model;

    const sidebarProps = {
        sessions: store.sessions.map<ChatSession>((session) => ({
            id: session.id,
            title: session.title,
            createdAt: new Date(session.createdAt),
            messageCount: session.messageCount,
        })),
        currentSessionId: store.currentSessionId ?? undefined,
        onSelectSession: handleSelectSession,
        onNewChat: handleNewChat,
        onDeleteSession: handleDeleteSession,
    };

    return (
        <div className="flex h-svh flex-col overflow-hidden bg-background">
            <AppHeader
                onOpenDocuments={() => setShowDocumentsPanel(true)}
                renderMobileSidebar={(close) => <SidebarContent {...sidebarProps} onAfterAction={close}/>}
            />
            <DocumentsPanel open={showDocumentsPanel} onClose={() => setShowDocumentsPanel(false)}/>

            <div className="flex min-h-0 flex-1">
                <AppSidebar {...sidebarProps}/>

                <main className="flex min-h-0 min-w-0 flex-1 flex-col">
                    {apiError && (
                        <ErrorBanner
                            error={apiError}
                            canRetry={Boolean(retryText)}
                            retrying={isLoading}
                            onRetry={handleRetry}
                            onDismiss={() => setApiError(null)}
                        />
                    )}

                    <ScrollArea className="min-h-0 flex-1">
                        <ChatMessages
                            messages={messages}
                            isLoading={isLoading}
                            citationFocus={citationFocus}
                            onCitationClick={handleCitationClick}
                            streamPhase={streamPhase}
                            requestStartedAt={requestStartedAt}
                            onRetry={retryText ? handleRetry : undefined}
                            bottomRef={scrollRef}
                        />
                    </ScrollArea>

                    <ChatComposer
                        value={input}
                        onChange={setInput}
                        onSend={handleSendMessage}
                        onStop={handleStopStreaming}
                        isLoading={isLoading}
                        streamingEnabled={STREAMING_ENABLED}
                        formError={formError}
                        maxTokens={maxTokens}
                        onMaxTokensChange={setMaxTokens}
                        temperature={temperature}
                        onTemperatureChange={setTemperature}
                        model={typeof activeModel === 'string' ? activeModel : undefined}
                    />
                </main>
            </div>
        </div>
    );
}
