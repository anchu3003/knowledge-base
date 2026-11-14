'use client';

import {useState} from 'react';
import {AlertTriangle, Copy} from 'lucide-react';

import {Button} from '@/components/ui/button';

import {Avatar, AvatarFallback} from '@/components/ui/avatar';
import {Skeleton} from '@/components/ui/skeleton';
import {MessageWithCitations} from '@/components/message-with-citations';
import {PiiBadge} from '@/components/pii-badge';
import {SourcesPanel} from '@/components/sources-panel';
import {StreamStatus} from '@/components/stream-status';
import {useToast} from '@/components/toast-provider';
import type {ChatMessage} from '@/lib/types';
import {EMPTY_ANSWER_HINT, type StreamPhase} from '@/lib/stream-phase';

/** Message type sống ở `lib/types.ts` (KB-4.9: `lib/chat-store.ts` cũng cần) — re-export cho chỗ cũ. */
export type {ChatMessage};

/**
 * Hàng hành động của một câu trả lời (hiện khi hover/focus). Nằm **ngoài** bubble nên không chiếm chỗ
 * bên trong và không đè lên chữ; feedback dùng `useToast` (KB-4.8) thay vì đổi text tại chỗ.
 */
function MessageActions({content}: {content: string}) {
    const {toast} = useToast();
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            toast({title: 'Đã sao chép câu trả lời'});
            setTimeout(() => setCopied(false), 2000);
        } catch {
            toast({
                title: 'Không sao chép được',
                description: 'Trình duyệt chặn clipboard (cần HTTPS hoặc localhost).',
                variant: 'destructive',
            });
        }
    };

    return (
        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
            <button
                type="button"
                onClick={handleCopy}
                aria-label="Sao chép câu trả lời"
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
                <Copy className="size-3"/>
                {copied ? 'Đã chép' : 'Sao chép'}
            </button>
        </div>
    );
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
    /** Pha hiện tại của lượt đang chạy (KB-4.11): `retrieving` trước `start`, `writing` sau `start`. */
    streamPhase?: StreamPhase;
    /** `Date.now()` lúc bấm gửi — dùng để đếm giây đã chờ. */
    requestStartedAt?: number | null;
    /** Gửi lại câu hỏi cuối (nút **Thử lại** ở thông báo answer rỗng). */
    onRetry?: () => void;
    /** Phần tử neo để auto-scroll xuống cuối (page giữ ref) */
    bottomRef?: React.Ref<HTMLDivElement>;
}

/**
 * Danh sách message (KB-4.8) — tách khỏi `page.tsx`.
 *
 * Thay đổi so với bản onboarding: bubble **full-width** (bỏ `max-w-md`), bỏ gradient tự phát,
 * dùng token `bg-card`/`text-card-foreground` ⇒ đọc được ở cả light và dark (KB-5.11: bỏ border mờ).
 */
export function ChatMessages({
    messages,
    isLoading,
    citationFocus,
    onCitationClick,
    streamPhase = 'idle',
    requestStartedAt = null,
    onRetry,
    bottomRef,
}: ChatMessagesProps) {
    const hasStreamingBubble = messages.some((message) => message.isStreaming);
    // KB-4.11: bubble stream **rỗng** (chưa có token nào) do `StreamStatus` đảm nhiệm ⇒ không render
    // cả hai (trước đây hiện thêm bubble "..." gây trùng lặp).
    const visibleMessages = messages.filter((message) => !(message.isStreaming && message.content.trim().length === 0));

    return (
        <div className="mx-auto w-full max-w-3xl space-y-6 px-3 py-6">
            {visibleMessages.map((message) => {
                const isUser = message.role === 'user';
                return (
                    <div
                        key={message.id}
                        className={`group flex items-start gap-2.5 ${isUser ? 'flex-row-reverse' : ''}`}
                    >
                        <Avatar className="mt-0.5 hidden sm:flex">
                            <AvatarFallback className={isUser ? 'bg-secondary text-secondary-foreground' : undefined}>
                                {isUser ? 'Bạn' : 'AI'}
                            </AvatarFallback>
                        </Avatar>

                        <div className={`flex min-w-0 max-w-full flex-1 flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
                            <div
                                data-testid={`bubble-${message.role}`}
                                className={`w-fit max-w-[88%] rounded-2xl px-3.5 py-2.5 shadow-xs ${
                                    isUser
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-card text-card-foreground'
                                }`}
                            >
                                {!isUser && (message.metadata?.pii_redacted_count ?? 0) > 0 && (
                                    <div className="mb-1.5">
                                        <PiiBadge count={message.metadata?.pii_redacted_count ?? 0}/>
                                    </div>
                                )}
                                {message.emptyAnswer ? (
                                    <div className="space-y-2" data-testid="empty-answer">
                                        <p className="flex items-center gap-2 text-sm font-medium text-amber-700 dark:text-amber-300">
                                            <AlertTriangle className="size-4 shrink-0"/>
                                            Model không trả về nội dung cho câu hỏi này
                                        </p>
                                        <p className="text-xs text-muted-foreground">{EMPTY_ANSWER_HINT}</p>
                                        {onRetry && (
                                            <Button size="sm" variant="outline" onClick={onRetry}>
                                                Thử lại
                                            </Button>
                                        )}
                                    </div>
                                ) : (
                                <MessageWithCitations
                                    content={message.content}
                                    isStreaming={message.isStreaming}
                                    isUser={isUser}
                                    messageId={message.id}
                                    stopped={message.stopped}
                                    onCitationClick={onCitationClick}
                                />
                                )}
                            </div>

                            {/* Hành động của message: nằm NGOÀI bubble (không chiếm chỗ / không đè chữ), hiện khi hover */}
                            {!isUser && <MessageActions content={message.content}/>}

                            {message.sources && message.sources.length > 0 && (
                                // gutter phải = avatar (2.25rem) + gap (0.625rem) để cạnh phải thẳng mép bubble user
                                <div className="w-full min-w-0 sm:pr-[2.875rem]">
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
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}

            {/* Pha truy hồi/đang viết (KB-4.11) — thay spinner câm; có số giây đã chờ */}
            {isLoading && (streamPhase === 'retrieving' || streamPhase === 'writing') && (
                <StreamStatus phase={streamPhase} startedAt={requestStartedAt ?? null}/>
            )}

            {/* Dự phòng: đang chờ nhưng chưa xác định được pha (vd. fallback blocking `/chat`) */}
            {isLoading && !hasStreamingBubble && streamPhase !== 'retrieving' && streamPhase !== 'writing' && (
                <div className="flex items-start gap-2.5">
                    <Avatar className="mt-0.5 hidden sm:flex">
                        <AvatarFallback>AI</AvatarFallback>
                    </Avatar>
                    <div className="w-full max-w-[calc(100%-1rem)] space-y-2 rounded-2xl bg-card px-3.5 py-3">
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
