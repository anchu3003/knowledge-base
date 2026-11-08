/**
 * API client duy nhất cho backend RAG (KB-4.1).
 *
 * Vì sao có file này: trước đây `app/page.tsx` gọi `fetch` inline, lỗi chỉ `console.error` + message tự chế
 * ⇒ không phân biệt được `429` (hết quota) vs `503/504` (provider) vs `422` (body sai). Backend (Phase 3) trả
 * contract thống nhất: `{"error": {"code", "message", "request_id"}}` + header `X-Request-ID`.
 *
 * Mọi lỗi mạng/HTTP được ném ra dưới dạng `ApiError` (có `code`, `requestId`, `status`) để UI map sang
 * message tiếng Việt (xem `lib/errors.ts`).
 */

import type { ChatRequest, ChatResponse } from './types';
import { createSseParser, isAbortError, parseChatEvent, type ChatStreamEvent } from './sse';

export const API_BASE_URL: string =
    (process.env.NEXT_PUBLIC_API_PROXY_URL as string) || 'http://localhost:8000';

export const REQUEST_ID_HEADER = 'X-Request-ID';

/** Code do FE tự sinh khi không có response HTTP (mất mạng, CORS, BE tắt). */
export const NETWORK_ERROR_CODE = 'network_error';
/** Code fallback khi response lỗi nhưng không parse được body theo contract. */
export const UNKNOWN_ERROR_CODE = 'internal_error';

export interface ApiErrorDetail {
    code?: string;
    message?: string;
    request_id?: string;
    details?: Array<Record<string, unknown>>;
}

export class ApiError extends Error {
    readonly code: string;
    readonly requestId: string;
    readonly status: number;
    readonly details?: Array<Record<string, unknown>>;

    constructor(params: {
        code: string;
        message: string;
        requestId?: string;
        status: number;
        details?: Array<Record<string, unknown>>;
    }) {
        super(params.message);
        this.name = 'ApiError';
        this.code = params.code;
        this.requestId = params.requestId || '-';
        this.status = params.status;
        this.details = params.details;
    }
}

/** `JSON.parse` an toàn — proxy/nginx có thể trả HTML thay vì JSON. */
function safeJson(text: string): Record<string, unknown> | null {
    if (!text) return null;
    try {
        const parsed = JSON.parse(text);
        return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
    } catch {
        return null;
    }
}

function toApiError(response: Response, rawBody: string): ApiError {
    const body = safeJson(rawBody);
    const detail = (body?.error ?? null) as ApiErrorDetail | null;
    const fallbackMessage = `Yêu cầu thất bại (HTTP ${response.status}).`;

    return new ApiError({
        code: typeof detail?.code === 'string' && detail.code ? detail.code : `http_${response.status}`,
        message: typeof detail?.message === 'string' && detail.message ? detail.message : fallbackMessage,
        requestId: detail?.request_id || response.headers.get(REQUEST_ID_HEADER) || '-',
        status: response.status,
        details: Array.isArray(detail?.details) ? detail!.details : undefined,
    });
}

/**
 * Gọi API và trả JSON đã parse. Ném `ApiError` cho mọi lỗi (mạng / HTTP / body sai contract).
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;

    try {
        response = await fetch(`${API_BASE_URL}${path}`, {
            ...init,
            headers: {
                'Content-Type': 'application/json',
                ...(init?.headers || {}),
            },
        });
    } catch (error) {
        // Mất mạng, CORS, BE tắt — không có status để đọc
        throw new ApiError({
            code: NETWORK_ERROR_CODE,
            message: 'Không kết nối được tới server.',
            status: 0,
        });
    }

    const rawBody = await response.text().catch(() => '');

    if (!response.ok) {
        throw toApiError(response, rawBody);
    }

    const parsed = safeJson(rawBody);
    if (parsed === null) {
        throw new ApiError({
            code: UNKNOWN_ERROR_CODE,
            message: 'Server trả về dữ liệu không đọc được.',
            requestId: response.headers.get(REQUEST_ID_HEADER) || '-',
            status: response.status,
        });
    }

    return parsed as T;
}

/** `POST /chat` — câu trả lời RAG (kèm `sources[]` + `metadata`). */
export async function postChat(body: ChatRequest, init?: RequestInit): Promise<ChatResponse> {
    return apiFetch<ChatResponse>('/chat', {
        method: 'POST',
        body: JSON.stringify(body),
        ...init,
    });
}

// ------------------------------
// Streaming SSE (KB-4.4)
// ------------------------------

/**
 * Streaming **bật mặc định** cho mọi câu hỏi (Q&A KB-4.4 Q2); `NEXT_PUBLIC_STREAMING=false` khi build
 * ⇒ quay lại `/chat` blocking, UI không đổi hành vi.
 */
export const STREAMING_ENABLED =
    (process.env.NEXT_PUBLIC_STREAMING ?? 'true').toString().toLowerCase() !== 'false';

/** Người dùng bấm **Stop** — không phải lỗi, UI không hiện banner lỗi. */
export class StreamAbortedError extends Error {
    constructor() {
        super('Stream aborted by user');
        this.name = 'StreamAbortedError';
    }
}

export interface StreamChatOptions {
    /** `AbortController.signal` — bấm Stop ⇒ `abort()` để huỷ request. */
    signal?: AbortSignal;
    /** Nhận từng event đã parse: `start` / `token` / `end` / `error`. */
    onEvent: (event: ChatStreamEvent) => void;
}

/**
 * `POST /chat/stream` — đọc SSE bằng `fetch` + `ReadableStream` reader (không dùng `EventSource` vì cần POST).
 *
 * - Frame bị cắt giữa 2 chunk / nhiều byte UTF-8 (tiếng Việt) ⇒ `TextDecoder({stream: true})` + parser buffer.
 * - Heartbeat `: ping` bị bỏ (xem `lib/sse.ts`).
 * - Bấm Stop ⇒ ném `StreamAbortedError` (phân biệt với lỗi mạng thật).
 * - HTTP lỗi trước khi stream ⇒ `ApiError` như `apiFetch` (cùng envelope `error.code`).
 */
export async function streamChat(
    body: ChatRequest,
    options: StreamChatOptions,
): Promise<void> {
    let response: Response;

    try {
        response = await fetch(`${API_BASE_URL}/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'text/event-stream',
            },
            body: JSON.stringify(body),
            signal: options.signal,
        });
    } catch (error) {
        if (isAbortError(error)) throw new StreamAbortedError();
        throw new ApiError({
            code: NETWORK_ERROR_CODE,
            message: 'Không kết nối được tới server.',
            status: 0,
        });
    }

    if (!response.ok) {
        throw toApiError(response, await response.text().catch(() => ''));
    }

    if (!response.body) {
        throw new ApiError({
            code: UNKNOWN_ERROR_CODE,
            message: 'Server không trả về stream đọc được.',
            requestId: response.headers.get(REQUEST_ID_HEADER) || '-',
            status: response.status,
        });
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const parser = createSseParser();

    const emit = (payloads: string[]) => {
        for (const payload of payloads) {
            const event = parseChatEvent(payload);
            if (event) options.onEvent(event);
        }
    };

    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            emit(parser.push(decoder.decode(value, { stream: true })));
        }
        // Ký tự UTF-8 còn dở trong decoder + frame cuối không có `\n\n`
        emit(parser.push(decoder.decode()));
        emit(parser.flush());
    } catch (error) {
        if (isAbortError(error) || options.signal?.aborted) throw new StreamAbortedError();
        throw error;
    } finally {
        reader.cancel().catch(() => undefined);
    }
}
