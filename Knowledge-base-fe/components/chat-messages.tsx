'use client';

import {Avatar, AvatarFallback} from '@/components/ui/avatar';
import {Skeleton} from '@/components/ui/skeleton';
import {MessageWithCitations} from '@/components/message-with-citations';
import {PiiBadge} from '@/components/pii-badge';
import {SourcesPanel} from '@/components/sources-panel';
import type {ChatMetadata, ChatSource} from '@/lib/types';

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    citations?: Array<{id: string; title: string; source: string; relevance: number}>;
    sources?: ChatSource[];
    metadata?: ChatMetadata;
    isStreaming?: boolean;
    /** Người dùng bấm **Stop** giữa lúc stream (KB-4.4) */
    stopped?: boolean;
}

/** Chip `[S#]` vừa bấm — panel nguồn của message đó scroll + highlight (KB-4.3). */
export interface CitationFocus {
    messageId: string;
    citationId: string;
    nonce: number;
}

interface ChatMessagesProps {
    messages: ChatMessage[];
    isLoading: boolean;
    citationFocus: CitationFocus | null;
    onCitationClick: (messageId: string, citationId: string) => void;
    /** Phần tử neo để auto-scroll xuống cuối (page giữ ref) */
    bottomRef?: React.Ref<HTMLDivElement>;
}

/**
 * Danh sách message (KB-4.8) — tách khỏi `page.tsx`.
 *
 * Thay đổi so với bản onboarding: bubble **full-width** (bỏ `max-w-md`), bỏ gradient tự phát,
 * dùng token `bg-card`/`border-border` ⇒ đọc được ở cả light và dark.
 */
export function ChatMessages({messages, isLoading, citationFocus, onCitationClick, bottomRef}: ChatMessagesProps) {
    const hasStreamingBubble = messages.some((message) => message.isStreaming);

    return (
        <div className="mx-auto w-full max-w-3xl space-y-6 px-3 py-6">
            {messages.map((message) => {
                const isUser = message.role === 'user';
                return (
                    <div
                        key={message.id}
                        className={`flex items-start gap-2.5 ${isUser ? 'flex-row-reverse' : ''}`}
                    >
                        <Avatar className="mt-0.5 hidden sm:flex">
                            <AvatarFallback className={isUser ? 'bg-secondary text-secondary-foreground' : undefined}>
                                {isUser ? 'Bạn' : 'AI'}
                            </AvatarFallback>
                        </Avatar>

                        <div className={`flex min-w-0 flex-1 flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
                            <div
                                className={`w-full max-w-[calc(100%-1rem)] rounded-2xl border px-3.5 py-2.5 shadow-xs ${
                                    isUser
                                        ? 'border-primary/30 bg-primary text-primary-foreground'
                                        : 'border-border bg-card text-card-foreground'
                                }`}
                            >
                                {!isUser && (message.metadata?.pii_redacted_count ?? 0) > 0 && (
                                    <div className="mb-1.5">
                                        <PiiBadge count={message.metadata?.pii_redacted_count ?? 0}/>
                                    </div>
                                )}
                                <MessageWithCitations
                                    content={message.content}
                                    isStreaming={message.isStreaming}
                                    citations={message.citations}
                                    isUser={isUser}
                                    stopped={message.stopped}
                                    onCitationClick={(citationId) => onCitationClick(message.id, citationId)}
                                />
                            </div>

                            {message.sources && message.sources.length > 0 && (
                                <SourcesPanel
                                    sources={message.sources}
                                    metadata={message.metadata}
                                    highlightCitationId={
                                        citationFocus?.messageId === message.id ? citationFocus.citationId : undefined
                                    }
                                    highlightNonce={
                                        citationFocus?.messageId === message.id ? citationFocus.nonce : undefined
                                    }
                                />
                            )}
                        </div>
                    </div>
                );
            })}

            {/* Chỉ hiện skeleton khi CHƯA có bubble stream (tránh 2 chỗ loading cùng lúc) */}
            {isLoading && !hasStreamingBubble && (
                <div className="flex items-start gap-2.5">
                    <Avatar className="mt-0.5 hidden sm:flex">
                        <AvatarFallback>AI</AvatarFallback>
                    </Avatar>
                    <div className="w-full max-w-[calc(100%-1rem)] space-y-2 rounded-2xl border border-border bg-card px-3.5 py-3">
                        <Skeleton className="h-3 w-1/3"/>
                        <Skeleton className="h-3 w-5/6"/>
                        <Skeleton className="h-3 w-2/3"/>
                    </div>
                </div>
            )}

            <div ref={bottomRef}/>
        </div>
    );
}
