import {afterEach, describe, expect, it, vi} from 'vitest';
import {
    ApiError,
    STREAMING_ENABLED,
    StreamAbortedError,
    clearDocuments,
    deleteConversation,
    getConversation,
    getDocumentsStatus,
    getFolderInfo,
    getHealth,
    getReady,
    listConversations,
    postChat,
    syncDocuments,
    streamChat,
} from '@/lib/api';

/** `Response` giả — chỉ cần đúng shape mà `apiFetch`/`streamChat` đọc. */
function makeResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
    const text = typeof body === 'string' ? body : JSON.stringify(body);
    return {
        ok: status >= 200 && status < 300,
        status,
        headers: {get: (name: string) => headers[name] ?? null},
        text: async () => text,
    } as unknown as Response;
}

/** Body giả lập `ReadableStream`: mỗi phần tử là một lần `read()` (frame có thể bị cắt giữa 2 lần). */
function streamResponse(chunks: string[], status = 200): Response {
    const encoder = new TextEncoder();
    let index = 0;
    return {
        ok: status >= 200 && status < 300,
        status,
        headers: {get: () => null},
        text: async () => '',
        body: {
            getReader: () => ({
                read: async () => (index >= chunks.length
                    ? {done: true, value: undefined}
                    : {done: false, value: encoder.encode(chunks[index++])}),
                cancel: async () => undefined,
            }),
        },
    } as unknown as Response;
}

function stubFetch(impl: (url: string, init?: RequestInit) => Promise<Response>) {
    const mock = vi.fn(impl);
    vi.stubGlobal('fetch', mock);
    return mock;
}

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('apiFetch — contract lỗi của BE (KB-4.1)', () => {
    it('parse envelope {error: {code, message, request_id}}', async () => {
        stubFetch(async () => makeResponse(429, {
            error: {code: 'provider_rate_limited', message: 'rate limited', request_id: 'req-1'},
        }, {'X-Request-ID': 'req-header'}));

        await expect(postChat({message: 'hi'})).rejects.toMatchObject({
            code: 'provider_rate_limited',
            requestId: 'req-1',
            status: 429,
        });
    });

    it('lỗi không theo contract ⇒ code http_<status> + request_id từ header', async () => {
        stubFetch(async () => makeResponse(503, 'gateway down', {'X-Request-ID': 'req-h'}));

        const error = await postChat({message: 'hi'}).catch((e) => e);
        expect(error).toBeInstanceOf(ApiError);
        expect(error.code).toBe('http_503');
        expect(error.requestId).toBe('req-h');
    });

    it('200 nhưng body là HTML ⇒ internal_error', async () => {
        stubFetch(async () => makeResponse(200, '<html>oops</html>'));

        await expect(postChat({message: 'hi'})).rejects.toMatchObject({code: 'internal_error'});
    });

    it('fetch ném ra (mất mạng/CORS) ⇒ network_error, status 0', async () => {
        stubFetch(async () => {
            throw new TypeError('Failed to fetch');
        });

        await expect(postChat({message: 'hi'})).rejects.toMatchObject({code: 'network_error', status: 0});
    });

    it('200 + JSON hợp lệ ⇒ trả payload', async () => {
        stubFetch(async () => makeResponse(200, {response: 'ok', conversation_id: 'c1'}));

        await expect(postChat({message: 'hi'})).resolves.toEqual({response: 'ok', conversation_id: 'c1'});
    });
});

describe('documents & health (KB-4.5)', () => {
    it('status/folder/health/clear gọi đúng endpoint + method', async () => {
        const mock = stubFetch(async () => makeResponse(200, {
            collection_name: 'kb', document_count: 3, status: 'healthy', message: 'cleared',
            folder_path: '/d', exists: true, uptime_seconds: 1, version: '1.0.0',
        }));

        await getDocumentsStatus();
        await getFolderInfo();
        await getHealth();
        await clearDocuments();

        const urls = mock.mock.calls.map((call) => String(call[0]));
        expect(urls).toEqual([
            expect.stringContaining('/documents/status'),
            expect.stringContaining('/documents/folder-info'),
            expect.stringContaining('/health'),
            expect.stringContaining('/documents/clear'),
        ]);
        expect((mock.mock.calls[3][1] as RequestInit).method).toBe('DELETE');
    });

    it('/ready trả 503 nhưng payload đúng schema ⇒ trả object, KHÔNG throw', async () => {
        stubFetch(async () => makeResponse(503, {
            status: 'error',
            checks: {provider_config: {ok: false, detail: 'missing config: OPENAI_API_KEY'}},
        }));

        const ready = await getReady();
        expect(ready.status).toBe('error');
        expect(ready.checks.provider_config.ok).toBe(false);
    });

    it('/ready trả body không đúng schema ⇒ ApiError (không im lặng)', async () => {
        stubFetch(async () => makeResponse(502, '<html>bad gateway</html>'));

        await expect(getReady()).rejects.toMatchObject({code: 'http_502'});
    });

    it('refresh 500 ⇒ document_store_error + request_id', async () => {
        stubFetch(async () => makeResponse(500, {
            error: {code: 'document_store_error', message: 'refresh failed', request_id: 'req-5'},
        }));

        await expect(syncDocuments()).rejects.toMatchObject({
            code: 'document_store_error',
            requestId: 'req-5',
        });
    });
});

describe('conversations (KB-5.2)', () => {
    it('list gọi GET /conversations và trả đúng shape', async () => {
        const mock = stubFetch(async () => makeResponse(200, {
            conversations: [{id: 'conv-1', title: 'Kafka', created_at: '', updated_at: '', message_count: 2}],
            total: 1,
        }));

        const result = await listConversations();

        expect(String(mock.mock.calls[0][0])).toContain('/conversations');
        expect(result.total).toBe(1);
        expect(result.conversations[0].id).toBe('conv-1');
    });

    it('getConversation encode id trên URL', async () => {
        const mock = stubFetch(async () => makeResponse(200, {
            id: 'conv/1', title: 't', created_at: '', updated_at: '', messages: [],
        }));

        await getConversation('conv/1');

        expect(String(mock.mock.calls[0][0])).toContain('/conversations/conv%2F1');
    });

    it('deleteConversation dùng method DELETE', async () => {
        const mock = stubFetch(async () => makeResponse(200, {message: 'Đã xoá hội thoại'}));

        await deleteConversation('conv-1');

        expect((mock.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
        expect(String(mock.mock.calls[0][0])).toContain('/conversations/conv-1');
    });

    it('xoá hội thoại không tồn tại ⇒ ApiError not_found (không im lặng)', async () => {
        stubFetch(async () => makeResponse(404, {
            error: {code: 'not_found', message: 'Resource not found.', request_id: 'req-9'},
        }));

        await expect(deleteConversation('khong-co')).rejects.toMatchObject({
            code: 'not_found',
            status: 404,
        });
    });
});

describe('streamChat (KB-4.4)', () => {
    it('đọc token qua nhiều chunk + bỏ heartbeat + chốt bằng end', async () => {
        stubFetch(async () => streamResponse([
            ': ping\n\ndata: {"type":"start","conversation_id":"c1"}\n\n',
            'data: {"type":"token","token":"Xin "}\n\ndata: {"type":"to',
            'ken","token":"chào"}\n\n: ping\n\n',
            'data: {"type":"end","answer":"Xin chào","sources":[{"citation_id":"S1"}]}\n\n',
        ]));

        const events: string[] = [];
        let answer = '';
        await streamChat({message: 'hi'}, {
            onEvent: (event) => {
                events.push(event.type);
                if (event.type === 'end') answer = event.answer ?? '';
            },
        });

        expect(events).toEqual(['start', 'token', 'token', 'end']);
        expect(answer).toBe('Xin chào');
    });

    it('abort ⇒ StreamAbortedError (không phải lỗi mạng)', async () => {
        const controller = new AbortController();
        stubFetch(async () => ({
            ok: true,
            status: 200,
            headers: {get: () => null},
            text: async () => '',
            body: {
                getReader: () => ({
                    read: async () => {
                        controller.abort();
                        const error = new Error('aborted');
                        error.name = 'AbortError';
                        throw error;
                    },
                    cancel: async () => undefined,
                }),
            },
        } as unknown as Response));

        await expect(streamChat({message: 'hi'}, {
            signal: controller.signal,
            onEvent: () => undefined,
        })).rejects.toBeInstanceOf(StreamAbortedError);
    });

    it('HTTP lỗi trước khi stream ⇒ ApiError theo envelope', async () => {
        stubFetch(async () => makeResponse(429, {
            error: {code: 'provider_rate_limited', message: 'x', request_id: 'r'},
        }));

        await expect(streamChat({message: 'hi'}, {onEvent: () => undefined}))
            .rejects.toMatchObject({code: 'provider_rate_limited'});
    });

    it('streaming bật mặc định (Q&A KB-4.4 Q2)', () => {
        expect(STREAMING_ENABLED).toBe(true);
    });
});

