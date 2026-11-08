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
