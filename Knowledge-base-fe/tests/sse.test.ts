import {describe, expect, it} from 'vitest';
import {createSseParser, isAbortError, parseChatEvent} from '@/lib/sse';

describe('createSseParser (KB-4.4)', () => {
    it('tách frame theo dòng trống + bỏ comment heartbeat `: ping`', () => {
        const parser = createSseParser();
        const frames = [
            ...parser.push(': ping\n\n'),
            ...parser.push('data: {"type":"token","token":"a"}\n\n'),
            ...parser.flush(),
        ];

        expect(frames).toEqual(['{"type":"token","token":"a"}']);
    });

    it('ghép frame bị cắt giữa 2 chunk', () => {
        const parser = createSseParser();
        expect(parser.push('data: {"type":"to')).toEqual([]);
        expect(parser.push('ken","token":"b"}\n\n')).toEqual(['{"type":"token","token":"b"}']);
    });

    it('nhiều frame trong 1 chunk + frame cuối thiếu dòng trống (chỉ nhả khi flush)', () => {
        const parser = createSseParser();
        const frames = parser.push('data: {"a":1}\n\ndata: {"b":2}\n\ndata: {"c":3}');
        expect(frames).toEqual(['{"a":1}', '{"b":2}']);

        expect(parser.flush()).toEqual(['{"c":3}']);
    });

    it('chuẩn hoá CRLF (proxy thêm \\r\\n)', () => {
        const parser = createSseParser();
        expect(parser.push('data: {"ok":true}\r\n\r\n')).toEqual(['{"ok":true}']);
    });

    it('frame chỉ có comment giữa stream ⇒ không sinh payload rỗng', () => {
        const parser = createSseParser();
        expect(parser.push(': ping\n\n: ping\n\n')).toEqual([]);
    });
});

describe('parseChatEvent (KB-4.4)', () => {
    it('map đúng 4 loại event của BE', () => {
        expect(parseChatEvent('{"type":"start","conversation_id":"c1","metadata":{"model":"m"}}'))
            .toMatchObject({type: 'start', conversation_id: 'c1'});
        expect(parseChatEvent('{"type":"token","token":"x"}')).toEqual({type: 'token', token: 'x'});
        expect(parseChatEvent('{"type":"end","answer":"a","sources":[{"citation_id":"S1"}]}'))
            .toMatchObject({type: 'end', answer: 'a'});
        expect(parseChatEvent('{"type":"error","error":{"code":"provider_timeout","message":"m","request_id":"r"}}'))
            .toEqual({type: 'error', error: {code: 'provider_timeout', message: 'm', request_id: 'r'}});
    });

    it('JSON hỏng / type lạ / token rỗng ⇒ null (không làm chết stream)', () => {
        expect(parseChatEvent('{oops')).toBeNull();
        expect(parseChatEvent('{"type":"whatever"}')).toBeNull();
        expect(parseChatEvent('   ')).toBeNull();
        expect(parseChatEvent('{"type":"token","token":""}')).toBeNull();
    });

    it('error thiếu field ⇒ giá trị mặc định an toàn', () => {
        expect(parseChatEvent('{"type":"error","error":{}}')).toEqual({
            type: 'error',
            error: {code: 'internal_error', message: '', request_id: '-'},
        });
    });
});

describe('isAbortError', () => {
    it('nhận AbortError/StreamAbortedError, không nhận lỗi khác', () => {
        const abort = new Error('x');
        abort.name = 'AbortError';

        expect(isAbortError(abort)).toBe(true);
        expect(isAbortError({name: 'StreamAbortedError'})).toBe(true);
        expect(isAbortError(new Error('boom'))).toBe(false);
        expect(isAbortError(null)).toBe(false);
    });
});
