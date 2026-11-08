'use client';

/**
 * Render markdown cho câu trả lời của assistant (KB-4.2).
 *
 * - `react-markdown` + `remark-gfm` + `rehype-highlight` (Q&A KB-4.2 chốt: có syntax highlighting).
 * - **Không** dùng `dangerouslySetInnerHTML`: react-markdown chỉ render AST → HTML thô trong nội dung
 *   (vd `<img onerror=…>`) hiện ra dạng text.
 * - Nhãn `[S1]` trong câu trả lời được đổi thành link `citation://S1` rồi render thành **chip bấm được**
 *   (callback `onCitationClick`, KB-4.3 sẽ nối vào panel nguồn).
 */

import {useMemo, useState} from 'react';
import ReactMarkdown, {type Components} from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import {Check, Copy} from 'lucide-react';

const CITATION_PATTERN = /\[(S\d{1,3})\]/g;
const CODE_SEGMENT = /(```[\s\S]*?```|`[^`\n]*`)/g;
/** Prefix anchor dùng nội bộ để chip citation; **không** dùng custom protocol (`citation://` bị react-markdown strip). */
const CITATION_HREF_PREFIX = '#citation-';

/**
 * Đổi `[S1]` → `[S1](#citation-S1)` nhưng **bỏ qua** code fence/inline code
 * (trong code, `[S1]` là dữ liệu, không phải citation).
 */
export function linkifyCitations(markdown: string): string {
    return markdown
        .split(CODE_SEGMENT)
        .map((part, index) =>
            index % 2 === 1
                ? part
                : part.replace(CITATION_PATTERN, (_match, id: string) => `[${id}](${CITATION_HREF_PREFIX}${id})`)
        )
        .join('');
}

interface HastNode {
    tagName?: string;
    value?: string;
    properties?: Record<string, unknown>;
    children?: HastNode[];
}

/** Lấy text thuần từ node hast (dùng để copy code block). */
export function nodeText(node?: HastNode): string {
    if (!node) return '';
    if (typeof node.value === 'string') return node.value;
    return (node.children || []).map(nodeText).join('');
}

function CodeBlock({language, code, children}: {
    language?: string;
    code: string;
    children: React.ReactNode;
}) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // clipboard bị chặn (http không bảo mật / quyền) — bỏ qua
        }
    };

    return (
        <div className="md-code my-3 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-slate-100/80 px-3 py-1.5 dark:border-slate-700 dark:bg-slate-800/80">
                <span className="font-mono text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    {language || 'code'}
                </span>
                <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium text-slate-600 transition hover:bg-slate-200/70 dark:text-slate-300 dark:hover:bg-slate-700/70"
                    aria-label="Copy code"
                >
                    {copied ? <Check className="h-3.5 w-3.5"/> : <Copy className="h-3.5 w-3.5"/>}
                    {copied ? 'Đã copy' : 'Copy'}
                </button>
            </div>
            <pre className="overflow-x-auto bg-slate-50 p-3 text-[13px] leading-relaxed dark:bg-slate-900">
                {children}
            </pre>
        </div>
    );
}

export interface MarkdownMessageProps {
    content: string;
    /** Bấm chip `[S#]` — KB-4.3 nối vào panel nguồn (scroll + highlight). */
    onCitationClick?: (citationId: string) => void;
}

export function MarkdownMessage({content, onCitationClick}: MarkdownMessageProps) {
    const prepared = useMemo(() => linkifyCitations(content || ''), [content]);

    const components = useMemo<Components>(() => ({
        pre: ({children, node}) => {
            const codeNode = (node?.children as HastNode[] | undefined)?.find(
                (child) => child.tagName === 'code'
            );
            const className = (codeNode?.properties?.className as string[] | undefined) || [];
            const language = className
                .find((name) => name.startsWith('language-'))
                ?.slice('language-'.length);

            return (
                <CodeBlock language={language} code={nodeText(codeNode)}>
                    {children}
                </CodeBlock>
            );
        },
        code: ({className, children}) => {
            const isBlock = typeof className === 'string' && className.includes('language-');
            if (isBlock) {
                // header + nút copy do `pre` đảm nhiệm, ở đây chỉ giữ span highlight
                return <code className={className}>{children}</code>;
            }
            return (
                <code className="rounded bg-slate-200/70 px-1 py-0.5 font-mono text-[0.85em] text-slate-800 dark:bg-slate-700/60 dark:text-slate-100">
                    {children}
                </code>
            );
        },
        a: ({href, children}) => {
            if (href && href.startsWith(CITATION_HREF_PREFIX)) {
                const citationId = href.slice(CITATION_HREF_PREFIX.length);
                return (
                    <button
                        type="button"
                        onClick={() => onCitationClick?.(citationId)}
                        aria-label={`Xem nguồn ${citationId}`}
                        className="mx-0.5 inline-flex items-center rounded-full border border-violet-300 bg-violet-50 px-1.5 py-0.5 align-baseline font-mono text-[0.75em] font-semibold text-violet-700 transition hover:bg-violet-100 dark:border-violet-700/60 dark:bg-violet-900/30 dark:text-violet-300 dark:hover:bg-violet-900/50"
                    >
                        {citationId}
                    </button>
                );
            }
            return (
                <a
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline underline-offset-2 hover:text-primary/80"
                >
                    {children}
                </a>
            );
        },
        table: ({children}) => (
            <div className="my-3 w-full overflow-x-auto">
                <table className="w-full border-collapse text-xs">{children}</table>
            </div>
        ),
        th: ({children}) => (
            <th className="border border-slate-200 bg-slate-100 px-2 py-1 text-left font-semibold dark:border-slate-700 dark:bg-slate-800">
                {children}
            </th>
        ),
        td: ({children}) => (
            <td className="border border-slate-200 px-2 py-1 align-top dark:border-slate-700">{children}</td>
        ),
        ul: ({children}) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
        ol: ({children}) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
        h1: ({children}) => <h3 className="mt-3 mb-1 text-base font-semibold">{children}</h3>,
        h2: ({children}) => <h4 className="mt-3 mb-1 text-sm font-semibold">{children}</h4>,
        h3: ({children}) => <h5 className="mt-2 mb-1 text-sm font-semibold">{children}</h5>,
        blockquote: ({children}) => (
            <blockquote className="my-2 border-l-2 border-slate-300 pl-3 italic text-slate-600 dark:border-slate-600 dark:text-slate-300">
                {children}
            </blockquote>
        ),
        hr: () => <hr className="my-3 border-slate-200 dark:border-slate-700"/>,
    }), [onCitationClick]);

    return (
        <div className="md-body">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[[rehypeHighlight, {detect: false, ignoreMissing: true}]]}
                components={components}
            >
                {prepared}
            </ReactMarkdown>
        </div>
    );
}
