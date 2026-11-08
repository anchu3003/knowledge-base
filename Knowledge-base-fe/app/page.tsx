'use client';

import {useEffect, useRef, useState} from 'react';

import {AppHeader} from '@/components/app-header';
import {AppSidebar, SidebarContent, type ChatSession} from '@/components/app-sidebar';
import {ChatComposer} from '@/components/chat-composer';
import {ChatMessages, type ChatMessage, type CitationFocus} from '@/components/chat-messages';
import {DocumentsPanel} from '@/components/documents-panel';
import {ErrorBanner} from '@/components/error-banner';
import {ScrollArea} from '@/components/ui/scroll-area';
import {ApiError, STREAMING_ENABLED, StreamAbortedError, postChat, streamChat} from '@/lib/api';
import {describeApiError, type ApiErrorView} from '@/lib/errors';

/** Key localStorage giữ `conversation_id` (Q&A KB-4.1: reload vẫn hỏi tiếp mạch). */
const CONVERSATION_STORAGE_KEY = 'kb.conversation_id';

/** Default khớp BE (`max_tokens=1000`) — bản onboarding gửi 500 (KB-4.9). */
const DEFAULT_MAX_TOKENS = 1000;
const DEFAULT_TEMPERATURE = 0.7;

/**
 * `createdAt` của session khởi tạo — tính **1 lần lúc import** thay vì trong render.
 * `react-hooks/purity` (KB-4.6) coi `Date.now()` trong render là impure ⇒ tách ra module scope.
 */
const INITIAL_SESSION_CREATED_AT = new Date(Date.now() - 86_400_000);

const GREETING =
    'Chào bạn! Mình là trợ lý trên kho tài liệu cá nhân của bạn. Hỏi mình bất cứ điều gì về tài liệu đã nạp ' +
    '(ghi chú kỹ thuật, ôn phỏng vấn, tài liệu tiếng Anh…).';

const INITIAL_MESSAGES: ChatMessage[] = [{id: 'greeting', role: 'assistant', content: GREETING}];

/**
 * Trang chat (KB-4.8 restructure).
 *
 * Chỉ giữ **state + logic** ở đây; phần hiển thị tách thành:
 * `AppHeader` (brand + theme + drawer mobile) · `AppSidebar` (sessions) · `ChatMessages` · `ChatComposer`
 * · `ErrorBanner` (KB-4.1) · `DocumentsPanel` (KB-4.5, giờ là `Sheet`).
 */
export default function ChatPage() {
    const [chatSessions, setChatSessions] = useState<ChatSession[]>([
        {
            id: 'session_1',
            title: 'Cuộc trò chuyện đầu tiên',
            createdAt: INITIAL_SESSION_CREATED_AT,
            messageCount: 1,
        },
    ]);
    const [currentSessionId, setCurrentSessionId] = useState('session_1');
    const [chatHistory, setChatHistory] = useState<Record<string, ChatMessage[]>>({
        session_1: INITIAL_MESSAGES,
    });
    const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
    const [input, setInput] = useState('');
    const [maxTokens, setMaxTokens] = useState<number>(DEFAULT_MAX_TOKENS);
    const [temperature, setTemperature] = useState<number>(DEFAULT_TEMPERATURE);
    const [formError, setFormError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    // KB-4.1: lỗi API hiển thị bằng banner (thay vì message giả trong khung chat)
    const [apiError, setApiError] = useState<ApiErrorView | null>(null);
    // Câu hỏi của lần gửi lỗi gần nhất — dùng cho nút "Thử lại" (không nhân đôi message user)
    const [retryText, setRetryText] = useState<string | null>(null);
    // `conversation_id` của BE, giữ qua reload bằng localStorage (Q&A KB-4.1)
    const [conversationId, setConversationId] = useState<string | null>(null);
    // KB-4.3: chip `[S#]` nào vừa được bấm ⇒ panel nguồn của message đó scroll + highlight card
    const [citationFocus, setCitationFocus] = useState<CitationFocus | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);
    // KB-4.4: controller của request đang stream — nút Stop gọi `abort()`
    const abortRef = useRef<AbortController | null>(null);
    // KB-4.5: drawer "Kho tài liệu" (status index + readiness + refresh/clear)
    const [showDocumentsPanel, setShowDocumentsPanel] = useState(false);

    // Auto-scroll xuống cuối mỗi khi có message mới
    useEffect(() => {
        scrollRef.current?.scrollIntoView({behavior: 'smooth'});
    }, [messages]);

    // Đồng bộ message hiện tại vào `chatHistory` của session đang mở
    useEffect(() => {
        if (currentSessionId && messages.length > 0) {
            setChatHistory((prev) => ({...prev, [currentSessionId]: messages}));
        }
    }, [messages, currentSessionId]);

    // Khôi phục `conversation_id` sau reload (chỉ đọc trong effect để không lệch SSR/hydration)
    useEffect(() => {
        try {
            const stored = window.localStorage.getItem(CONVERSATION_STORAGE_KEY);
            if (stored && stored.length > 0) {
                setConversationId(stored);
            }
        } catch {
            // localStorage bị chặn (private mode) — bỏ qua, dùng conversation_id do BE trả về
        }
    }, []);

    useEffect(() => {
        if (!conversationId) return;
        try {
            window.localStorage.setItem(CONVERSATION_STORAGE_KEY, conversationId);
        } catch {
            // bỏ qua
        }
    }, [conversationId]);

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
        setMessages((prev) => prev.map((message) => (message.id === id ? updater(message) : message)));
    };

    /** Bỏ bubble assistant rỗng (lỗi/Stop trước khi có token nào) — không để khung chat trống trơn. */
    const dropIfEmpty = (id: string) => {
        setMessages((prev) => prev.filter((message) => !(message.id === id && message.content.trim().length === 0)));
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

        if (options.appendUserMessage) {
            setMessages((prev) => [...prev, {id: Date.now().toString(), role: 'user', content: question}]);
            setChatSessions((prev) =>
                prev.map((session) =>
                    session.id === currentSessionId
                        ? {...session, messageCount: session.messageCount + 1}
                        : session,
                ),
            );
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
                        id: (Date.now() + 1).toString(),
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
            }
            return;
        }


        // ---- Mặc định: streaming SSE `POST /chat/stream` (KB-4.4) ----
        const assistantId = `assistant-${Date.now()}`;
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
                            updateAssistant(assistantId, (message) => ({
                                ...message,
                                content: event.answer ?? message.content,
                                sources: event.sources ?? message.sources,
                                metadata: event.metadata ?? message.metadata,
                                isStreaming: false,
                            }));
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
        setCitationFocus((prev) => ({messageId, citationId, nonce: (prev?.nonce ?? 0) + 1}));
    };

    const handleSelectSession = (sessionId: string) => {
        // Lưu message hiện tại vào history trước khi chuyển
        if (currentSessionId && messages.length > 0) {
            setChatHistory((prev) => ({...prev, [currentSessionId]: messages}));
        }

        setCurrentSessionId(sessionId);
        setMessages(chatHistory[sessionId] ?? INITIAL_MESSAGES);
        setApiError(null);
        setRetryText(null);
    };

    const handleNewChat = () => {
        if (currentSessionId && messages.length > 0) {
            setChatHistory((prev) => ({...prev, [currentSessionId]: messages}));
        }

        const newSession: ChatSession = {
            id: `session_${Date.now()}`,
            title: 'Cuộc trò chuyện mới',
            createdAt: new Date(),
            messageCount: 0,
        };
        setChatSessions((prev) => [newSession, ...prev]);
        setCurrentSessionId(newSession.id);
        // KB-4.1: chat mới ⇒ conversation_id mới (BE sẽ cấp id khác) — xoá id cũ khỏi localStorage
        setConversationId(null);
        setApiError(null);
        setRetryText(null);
        try {
            window.localStorage.removeItem(CONVERSATION_STORAGE_KEY);
        } catch {
            // bỏ qua
        }
        setMessages(INITIAL_MESSAGES);
    };

    const handleDeleteSession = (sessionId: string) => {
        setChatSessions((prev) => prev.filter((session) => session.id !== sessionId));
        setChatHistory((prev) => {
            const next = {...prev};
            delete next[sessionId];
            return next;
        });
        if (currentSessionId === sessionId) {
            const remaining = chatSessions.filter((session) => session.id !== sessionId);
            if (remaining.length > 0) {
                setCurrentSessionId(remaining[0].id);
                setMessages(chatHistory[remaining[0].id] ?? INITIAL_MESSAGES);
            } else {
                handleNewChat();
            }
        }
    };

    // Model thật BE đã dùng (metadata của câu trả lời gần nhất) — không phải select giả như bản cũ
    const activeModel = [...messages]
        .reverse()
        .find((message) => message.role === 'assistant' && message.metadata?.model)?.metadata?.model;

    const sidebarProps = {
        sessions: chatSessions,
        currentSessionId,
        onSelectSession: handleSelectSession,
        onNewChat: handleNewChat,
        onDeleteSession: handleDeleteSession,
        onOpenDocuments: () => setShowDocumentsPanel(true),
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

