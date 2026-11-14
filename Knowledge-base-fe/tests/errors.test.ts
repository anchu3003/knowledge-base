import {describe, expect, it} from 'vitest';
import {ApiError} from '@/lib/api';
import {describeApiError} from '@/lib/errors';

function apiError(code: string, status = 400, requestId = 'req-1') {
    return new ApiError({code, message: 'server message', status, requestId});
}

describe('describeApiError (KB-4.1)', () => {
    it('map code của BE sang message tiếng Việt + giữ request_id', () => {
        const view = describeApiError(apiError('provider_rate_limited', 429, 'req-9'));

        expect(view.code).toBe('provider_rate_limited');
        expect(view.message).toContain('hạn mức');
        expect(view.requestId).toBe('req-9');
        expect(view.retryable).toBe(true);
    });

    it('code không retry được ⇒ retryable=false', () => {
        expect(describeApiError(apiError('document_store_error', 500)).retryable).toBe(false);
        expect(describeApiError(apiError('validation_error', 422)).retryable).toBe(false);
    });

    it('timeout của FE có message riêng, không phải "không kết nối được" (KB-4.5)', () => {
        const view = describeApiError(apiError('request_timeout', 0));

        expect(view.message).toContain('quá lâu');
        expect(view.retryable).toBe(false);
    });

    it('code lạ ⇒ fallback theo HTTP status (429/503 retryable)', () => {
        const retryable = describeApiError(apiError('code_moi_cua_be', 503));
        expect(retryable.retryable).toBe(true);
        expect(retryable.hint).toContain('503');

        expect(describeApiError(apiError('code_moi_cua_be', 400)).retryable).toBe(false);
    });

    it('lỗi không phải ApiError ⇒ internal_error phía trình duyệt', () => {
        const view = describeApiError(new Error('boom'));

        expect(view.code).toBe('internal_error');
        expect(view.message).toContain('trình duyệt');
        expect(view.requestId).toBe('-');
    });
});
