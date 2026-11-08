'use client';

import {Card, CardContent} from '@/components/ui/card';
import {Copy, ExternalLink} from 'lucide-react';
import {TypingIndicator} from './typing-indicator';
import {MarkdownMessage} from './markdown-message';
import {useState} from 'react';

interface Citation {
    id: string;
    title: string;
    source: string;
    relevance: number;
}

interface Source {
    file_path: string;
    file_name: string;
    file_type: string;
    relevance_score: number;
    content_preview?: string;
    snippet?: string;
    citation_id?: string;
    chunk_id?: string;
    heading_path?: string;
}

interface MessageWithCitationsProps {
    content: string;
    isStreaming?: boolean;
    citations?: Citation[];
    sources?: Source[];
    isUser?: boolean;
    /** Bấm chip `[S#]` trong câu trả lời (KB-4.2; KB-4.3 nối vào panel nguồn). */
    onCitationClick?: (citationId: string) => void;
    /** Người dùng bấm **Stop** giữa lúc stream (KB-4.4) — text đã nhận vẫn giữ, chỉ thêm nhãn. */
    stopped?: boolean;
}

export function MessageWithCitations({
                                         content,
                                         isStreaming = false,
                                         citations = [],
                                         sources = [],
                                         isUser = false,
                                         onCitationClick,
                                         stopped = false,
                                     }: MessageWithCitationsProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // clipboard bị chặn — bỏ qua
        }
    };
    return (
        <div className="relative space-y-3">
            {/* KB-4.8: bỏ bubble riêng ở đây — `ChatMessages` đã là bubble ⇒ tránh "bubble lồng bubble" + `max-w-md` */}
            <div className="relative">
                {/* Actions: copy */}
                {!isUser && (
                    <button
                        onClick={handleCopy}
                        aria-label="Sao chép câu trả lời"
                        className="absolute top-1 right-1 z-30 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted/60"
                        title="Sao chép câu trả lời"
                    >
                        <Copy className="h-3.5 w-3.5"/>
                        <span>{copied ? 'Đã chép' : 'Sao chép'}</span>
                    </button>
                )}

                <div className="pr-16">
                    {isUser ? (
                        <p className="break-words whitespace-pre-wrap">{content}</p>
                    ) : (
                        <MarkdownMessage content={content} onCitationClick={onCitationClick}/>
                    )}
                </div>
                {isStreaming && <TypingIndicator/>}
                {stopped && !isStreaming && (
                    <p className="mt-2 text-xs font-medium text-amber-600 dark:text-amber-400">
                        ⏹ Đã dừng — câu trả lời chỉ gồm phần đã nhận.
                    </p>
                )}
            </div>

            {/* Sources (new format) */}
            {!isUser && sources.length > 0 && (
                <div className="space-y-2 ml-4">
                    <p className="text-xs font-medium text-muted-foreground">
                        📚 Sources ({sources.length}):
                    </p>
                    <div className="space-y-2">
                        {sources.map((source, idx) => (
                            <Card
                                key={`${source.file_path}-${idx}`}
                                className="border border-border/50 bg-muted/30"
                            >
                                <CardContent className="p-3">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1">
                                                <p className="text-xs font-semibold text-foreground">
                                                    {source.file_name}
                                                </p>
                                                <span
                                                    className="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary font-mono">
                                                    {source.file_type}
                                                 </span>
                                            </div>
                                            <p
                                                className="text-xs text-muted-foreground truncate mb-2"
                                                title={source.file_path}
                                            >
                                                {source.file_path}
                                            </p>
                                            <div className="mt-1 flex items-center gap-2">
                                                <div className="h-1.5 flex-1 bg-border rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-gradient-to-r from-violet-500 to-purple-500"
                                                        style={{
                                                            width: `${source.relevance_score * 100}%`,
                                                        }}
                                                    />
                                                </div>
                                                <span
                                                    className="text-xs font-medium text-muted-foreground whitespace-nowrap">
                                                    {(source.relevance_score * 100).toFixed(1)}%
                                                </span>
                                            </div>
                                            {source.content_preview && (
                                                <details className="mt-2 text-xs">
                                                    <summary
                                                        className="cursor-pointer text-primary hover:text-primary/80 font-medium">
                                                        Preview
                                                    </summary>
                                                    <pre
                                                        className="mt-1 p-2 rounded bg-muted text-xs whitespace-pre-wrap break-words">
                                                        {source.content_preview}
                                                    </pre>
                                                </details>
                                            )}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            )}

            {/* Citations (legacy format, keep for backward compatibility) */}
            {!isUser && citations.length > 0 && (
                <div className="space-y-2 ml-4">
                    <p className="text-xs font-medium text-muted-foreground">Sources:</p>
                    <div className="space-y-2">
                        {citations.map((citation) => (
                            <Card
                                key={citation.id}
                                className="border border-border/50 bg-muted/30"
                            >
                                <CardContent className="p-3">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-medium text-foreground truncate">
                                                {citation.title}
                                            </p>
                                            <p className="text-xs text-muted-foreground truncate">
                                                {citation.source}
                                            </p>
                                            <div className="mt-1 flex items-center gap-1">
                                                <div className="h-1 flex-1 bg-border rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-primary"
                                                        style={{width: `${citation.relevance * 100}%`}}
                                                    />
                                                </div>
                                                <span className="text-xs text-muted-foreground">
                                                    {Math.round(citation.relevance * 100)}%
                                                </span>
                                            </div>
                                        </div>
                                        <a
                                            href="#"
                                            className="text-primary hover:text-primary/80 transition flex-shrink-0"
                                            title="View source"
                                        >
                                            <ExternalLink className="h-4 w-4"/>
                                        </a>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
