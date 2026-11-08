/**
 * Parser SSE cho `POST /chat/stream` (KB-4.4) — **thuần**, không đụng `fetch`/DOM ⇒ test được bằng `node`.
 *
 * Contract của BE (KB-3.3, `app/core/sse.py`):
 * - mỗi event là `data: <json>\n\n`;
 * - heartbeat là comment `: ping\n\n` (không phải event ⇒ **phải bỏ**, nếu không sẽ tạo message rỗng);
 * - event: `start {conversation_id, metadata}` → `token {token}`* → `end {answer, sources, metadata}` | `error {error}`.
 *
 * Vì sao tự parse thay vì `EventSource`: cần POST + body JSON (EventSource chỉ GET).
 */

import type {ChatMetadata, ChatSource} from './types';

export type ChatStreamEvent =
    | {type: 'start'; conversation_id?: string; metadata?: ChatMetadata}
    | {type: 'token'; token: string}
    | {
    type: 'end';
    answer?: string;
    conversation_id?: string;
    sources?: ChatSource[];
    metadata?: ChatMetadata;
}
    | {type: 'error'; error: {code: string; message: string; request_id: string}};

export interface SseParser {
    /** Nạp một chunk text, trả về payload của các frame đã **hoàn chỉnh**. */
    push(chunk: string): string[];
    /** Kết thúc stream: nhả frame cuối nếu BE không gửi `\n\n` đóng. */
    flush(): string[];
}

/**
 * Tách frame theo `\n\n`. Buffer lại phần dở giữa 2 chunk (frame có thể bị cắt bất kỳ chỗ nào).
 * Bỏ qua frame chỉ có comment/heartbeat.
 */
export function createSseParser(): SseParser {
    let buffer = '';

    const extract = (final: boolean): string[] => {
        const payloads: string[] = [];
        let index = buffer.indexOf('\n\n');
        while (index !== -1) {
            const payload = frameData(buffer.slice(0, index));
            buffer = buffer.slice(index + 2);
            if (payload !== null) payloads.push(payload);
            index = buffer.indexOf('\n\n');
        }
        if (final && buffer.trim().length > 0) {
            const payload = frameData(buffer);
            buffer = '';
            if (payload !== null) payloads.push(payload);
        }
        return payloads;
    };

    return {
        push(chunk: string): string[] {
            // SSE cho phép CRLF (proxy có thể thêm) — chuẩn hoá rồi mới cắt bằng `\n\n`
            buffer += chunk.replace(/\r\n/g, '\n');
            return extract(false);
        },
        flush(): string[] {
            return extract(true);
        },
    };
}

/** Lấy payload `data:` của một frame; frame chỉ có comment (`: ping`) ⇒ `null`. */
function frameData(frame: string): string | null {
    const dataLines: string[] = [];

    for (const line of frame.split('\n')) {
        if (line.startsWith(':')) continue; // heartbeat/comment
        if (line.length === 0) continue;
        if (line.startsWith('data:')) {
            dataLines.push(line.slice('data:'.length).replace(/^ /, ''));
        }
    }

    if (dataLines.length === 0) return null;
    return dataLines.join('\n');
}

function asString(value: unknown): string | undefined {
    return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function asMetadata(value: unknown): ChatMetadata | undefined {
    return value && typeof value === 'object' ? (value as ChatMetadata) : undefined;
}

function asSources(value: unknown): ChatSource[] | undefined {
    return Array.isArray(value) ? (value as ChatSource[]) : undefined;
}

/** JSON payload → event có type. JSON hỏng / type lạ ⇒ `null` (bỏ qua, không làm chết stream). */
export function parseChatEvent(payload: string): ChatStreamEvent | null {
    const trimmed = payload.trim();
    if (!trimmed) return null;

    let parsed: unknown;
    try {
        parsed = JSON.parse(trimmed);
    } catch {
        return null;
    }
    if (!parsed || typeof parsed !== 'object') return null;

    const event = parsed as Record<string, unknown>;

    switch (event.type) {
        case 'start':
            return {
                type: 'start',
                conversation_id: asString(event.conversation_id),
                metadata: asMetadata(event.metadata),
            };
        case 'token': {
            const token = asString(event.token);
            // token rỗng ⇒ không có gì để hiện, bỏ (tránh re-render vô ích)
            return token === undefined ? null : {type: 'token', token};
        }
        case 'end':
            return {
                type: 'end',
                answer: typeof event.answer === 'string' ? event.answer : undefined,
                conversation_id: asString(event.conversation_id),
                sources: asSources(event.sources),
                metadata: asMetadata(event.metadata),
            };
        case 'error': {
            const detail = (event.error ?? {}) as Record<string, unknown>;
            return {
                type: 'error',
                error: {
                    code: asString(detail.code) ?? 'internal_error',
                    message: asString(detail.message) ?? '',
                    request_id: asString(detail.request_id) ?? '-',
                },
            };
        }
        default:
            return null;
    }
}

/** `AbortController.abort()` làm `fetch`/`reader.read()` ném `AbortError` — người dùng bấm Stop, không phải lỗi mạng. */
export function isAbortError(error: unknown): boolean {
    if (!error || typeof error !== 'object') return false;
    const name = (error as {name?: string}).name;
    return name === 'AbortError' || name === 'StreamAbortedError';
}
