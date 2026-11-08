'use client';

/**
 * Panel nguồn tham khảo của một câu trả lời (KB-4.3).
 *
 * - BE trả `sources[]` **theo chunk**, mỗi phần tử có `citation_id` (`S1..Sk`), `chunk_id`, `heading_path`,
 *   `snippet` ⇒ panel render **1 card / chunk**, **không** dedup theo `file_path` (trả **TD-12**).
 * - Bấm chip `[S#]` trong câu trả lời (KB-4.2) ⇒ page truyền `highlightCitationId` + `highlightNonce`
 *   xuống ⇒ panel scroll card đó vào view + highlight ~2s.
 * - Key React là `citation_id` (BE sinh **theo từng response**), không dùng index của mảng.
 */

import {useEffect, useRef, useState} from 'react';
import {ChevronDown, ChevronUp, FileText, Star} from 'lucide-react';
import type {ChatMetadata, ChatSource} from '@/lib/types';

/** Giả định (c) của ticket: snippet hiện tối đa ~400 ký tự rồi "Xem thêm". */
const SNIPPET_PREVIEW_LENGTH = 400;
/** Highlight card được bấm trong bao lâu (ms). */
const HIGHLIGHT_DURATION_MS = 2000;
/** `chunk_id` hiển thị dạng ngắn (AC: ≥ 8 ký tự). */
const CHUNK_ID_SHORT_LENGTH = 8;

/** `[S#]` của một source: ưu tiên `citation_id` của BE, fallback theo thứ tự (BE cũ chưa có field này). */
export function citationLabel(source: ChatSource, index: number): string {
    return source.citation_id && source.citation_id.length > 0 ? source.citation_id : `S${index + 1}`;
}

/** Rút gọn `chunk_id` để hiện badge `chunk #abcdef12` (null khi BE cũ không trả). */
export function shortChunkId(chunkId?: string): string | null {
    if (!chunkId) return null;
    return chunkId.slice(0, CHUNK_ID_SHORT_LENGTH);
}

export interface SnippetView {
    text: string;
    /** Có bị cắt bớt (cần nút "Xem thêm") hay không. */
    truncated: boolean;
}

/** Text hiển thị của một nguồn: ưu tiên `snippet` (KB-2.3), fallback `content_preview` (BE cũ). */
export function snippetView(source: ChatSource, expanded: boolean): SnippetView {
    const raw = (source.snippet || source.content_preview || '').trim();
    if (raw.length <= SNIPPET_PREVIEW_LENGTH) {
        return {text: raw, truncated: false};
    }
    return {
        text: expanded ? raw : `${raw.slice(0, SNIPPET_PREVIEW_LENGTH)}…`,
        truncated: true,
    };
}

/** Dòng phụ đề: `Java > Collections` (heading_path) hoặc đường dẫn file. */
export function sourceSubtitle(source: ChatSource): string {
    return source.heading_path && source.heading_path.trim().length > 0
        ? source.heading_path.trim()
        : source.file_path;
}

interface SourcesPanelProps {
    /** `sources` của BE, **giữ nguyên thứ tự + không dedup** (mỗi phần tử là 1 chunk). */
    sources: ChatSource[];
    metadata?: ChatMetadata;
    /** Chip `[S#]` vừa được bấm (KB-4.2 → KB-4.3). */
    highlightCitationId?: string;
    /** Nonce tăng mỗi lần bấm ⇒ bấm lại cùng một chip vẫn scroll/highlight lại. */
    highlightNonce?: number;
}

export function SourcesPanel({
                                 sources,
                                 metadata,
                                 highlightCitationId,
                                 highlightNonce,
                             }: SourcesPanelProps) {
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});
    // Khởi tạo từ prop để card đúng được highlight ngay từ render đầu (không nháy), đồng thời SSR verify được.
    const [highlighted, setHighlighted] = useState<string | null>(highlightCitationId ?? null);
    const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

    // Scroll + highlight card khi bấm chip `[S#]` trong câu trả lời.
    useEffect(() => {
        if (!highlightCitationId) return;
        const card = cardRefs.current[highlightCitationId];
        if (!card) return;
        card.scrollIntoView({behavior: 'smooth', block: 'center'});
        setHighlighted(highlightCitationId);
        const timer = setTimeout(
            () => setHighlighted((current) => (current === highlightCitationId ? null : current)),
            HIGHLIGHT_DURATION_MS
        );
        return () => clearTimeout(timer);
    }, [highlightCitationId, highlightNonce]);

    if (sources.length === 0) return null;

    const model = typeof metadata?.model === 'string' ? metadata.model : null;
    const retrieved = typeof metadata?.retrieved_documents === 'number' ? metadata.retrieved_documents : null;

    return (
        <section className="mt-4 space-y-2" aria-label="Nguồn tham khảo">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400">
                <FileText className="h-4 w-4"/>
                <span>Nguồn ({sources.length})</span>
            </div>

            <div className="space-y-2">
                {sources.map((source, index) => (
                    <SourceCard
                        key={citationLabel(source, index)}
                        source={source}
                        index={index}
                        expanded={expanded[citationLabel(source, index)] ?? false}
                        highlighted={highlighted === citationLabel(source, index)}
                        onToggle={() =>
                            setExpanded((prev) => ({
                                ...prev,
                                [citationLabel(source, index)]: !prev[citationLabel(source, index)],
                            }))
                        }
                        registerRef={(node) => {
                            cardRefs.current[citationLabel(source, index)] = node;
                        }}
                    />
                ))}
            </div>

            {(model || retrieved !== null) && (
                <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-slate-500 dark:text-slate-400">
                    {model && <span className="font-mono">{model}</span>}
                    {model && retrieved !== null && <span aria-hidden="true">·</span>}
                    {retrieved !== null && <span>{retrieved} tài liệu đã truy hồi</span>}
                    {/* PiiBadge giữ ở header message (KB-1.3) để không lặp icon khi có nguồn — xem Backlog KB-4.3. */}
                </div>
            )}
        </section>
    );
}

interface SourceCardProps {
    source: ChatSource;
    index: number;
    expanded: boolean;
    highlighted: boolean;
    onToggle: () => void;
    registerRef: (node: HTMLDivElement | null) => void;
}

/** Một nguồn = **một chunk** (Q&A KB-4.3 chốt: không gộp theo file). */
function SourceCard({source, index, expanded, highlighted, onToggle, registerRef}: SourceCardProps) {
    const label = citationLabel(source, index);
    const chunk = shortChunkId(source.chunk_id);
    const {text, truncated} = snippetView(source, expanded);

    return (
        <div
            ref={registerRef}
            data-testid={`source-card-${label}`}
            data-citation-id={label}
            className={`rounded-xl border p-3 shadow-sm transition-all ${
                highlighted
                    ? 'border-violet-400 bg-violet-50 ring-2 ring-violet-300 dark:border-violet-500 dark:bg-violet-900/30 dark:ring-violet-700'
                    : 'border-slate-200 bg-white hover:shadow-md dark:border-slate-700 dark:bg-slate-800'
            }`}
        >
            <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500/10 to-purple-500/10">
                    <FileText className="h-4 w-4 text-violet-600 dark:text-violet-400"/>
                </div>

                <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center rounded-full border border-violet-300 bg-violet-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-violet-700 dark:border-violet-700/60 dark:bg-violet-900/30 dark:text-violet-300">
                            [{label}]
                        </span>
                        <h4 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                            {source.file_name}
                        </h4>
                        <span className="inline-flex flex-shrink-0 items-center rounded-md bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">
                            {source.file_type}
                        </span>
                        {chunk && (
                            <span
                                className="inline-flex flex-shrink-0 items-center rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-600 dark:bg-slate-700/60 dark:text-slate-300"
                                title={source.chunk_id}
                            >
                                chunk #{chunk}
                            </span>
                        )}
                    </div>

                    <p className="mb-2 truncate text-xs text-slate-500 dark:text-slate-400"
                       title={sourceSubtitle(source)}>
                        {sourceSubtitle(source)}
                    </p>

                    {text && (
                        <p className="whitespace-pre-wrap break-words text-xs text-slate-600 dark:text-slate-300">
                            {text}
                        </p>
                    )}

                    <div className="mt-2 flex items-center gap-3">
                        <span className="inline-flex items-center gap-1">
                            <Star className="h-3.5 w-3.5 text-amber-500" fill="currentColor"/>
                            <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                Score: {(source.relevance_score ?? 0).toFixed(3)}
                            </span>
                        </span>
                        {truncated && (
                            <button
                                type="button"
                                onClick={onToggle}
                                aria-expanded={expanded}
                                className="inline-flex items-center gap-1 text-xs font-medium text-violet-700 hover:underline dark:text-violet-300"
                            >
                                {expanded ? (
                                    <>
                                        Thu gọn <ChevronUp className="h-3.5 w-3.5"/>
                                    </>
                                ) : (
                                    <>
                                        Xem thêm <ChevronDown className="h-3.5 w-3.5"/>
                                    </>
                                )}
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

