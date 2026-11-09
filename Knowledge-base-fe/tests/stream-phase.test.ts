import {describe, expect, it} from 'vitest';
import {
    EMPTY_ANSWER_HINT,
    formatSeconds,
    phaseLabel,
    phaseLabelWithElapsed,
    phaseOf,
} from '@/lib/stream-phase';

describe('phaseOf (KB-4.11)', () => {
    it('chưa gửi gì ⇒ idle', () => {
        expect(phaseOf({loading: false, started: false, finished: false})).toBe('idle');
    });

    it('đang chờ, CHƯA có event start ⇒ retrieving (pha chậm ~8-13s của rerank)', () => {
        expect(phaseOf({loading: true, started: false, finished: false})).toBe('retrieving');
    });

    it('đã có event start ⇒ writing', () => {
        expect(phaseOf({loading: true, started: true, finished: false})).toBe('writing');
    });

    it('đã finished + answer có nội dung ⇒ done', () => {
        expect(phaseOf({loading: false, started: true, finished: true})).toBe('done');
        expect(phaseOf({loading: false, started: true, finished: true, answerEmpty: false})).toBe('done');
    });

    it('finished + answer rỗng ⇒ empty', () => {
        expect(phaseOf({loading: false, started: true, finished: true, answerEmpty: true})).toBe('empty');
    });

    it('answerEmpty không được "thắng" khi còn đang chạy', () => {
        // BE chưa gửi end thì chưa thể kết luận rỗng
        expect(phaseOf({loading: true, started: true, finished: false, answerEmpty: true})).toBe('writing');
        expect(phaseOf({loading: true, started: false, finished: false, answerEmpty: true})).toBe('retrieving');
    });

    it('finished thắng loading (request đã xong nhưng state loading chưa kịp reset)', () => {
        expect(phaseOf({loading: true, started: true, finished: true})).toBe('done');
    });
});

describe('nhãn & thời gian (KB-4.11)', () => {
    it('nhãn tiếng Việt từng pha', () => {
        expect(phaseLabel('retrieving')).toBe('Đang truy hồi tài liệu…');
        expect(phaseLabel('writing')).toBe('Đang viết câu trả lời…');
        expect(phaseLabel('empty')).toBe('Model không trả về nội dung');
        expect(phaseLabel('idle')).toBe('');
        expect(phaseLabel('done')).toBe('');
    });

    it('formatSeconds làm tròn xuống và không âm', () => {
        expect(formatSeconds(0)).toBe('0s');
        expect(formatSeconds(999)).toBe('0s');
        expect(formatSeconds(1000)).toBe('1s');
        expect(formatSeconds(12_859)).toBe('12s');
        expect(formatSeconds(-500)).toBe('0s');
    });

    it('phaseLabelWithElapsed ghép nhãn + số giây', () => {
        expect(phaseLabelWithElapsed('retrieving', 7000)).toBe('Đang truy hồi tài liệu… (7s)');
        expect(phaseLabelWithElapsed('writing', 1500)).toBe('Đang viết câu trả lời… (1s)');
    });

    it('pha không cần hiển thị ⇒ chuỗi rỗng ( để component trả null)', () => {
        expect(phaseLabelWithElapsed('idle', 5000)).toBe('');
        expect(phaseLabelWithElapsed('done', 5000)).toBe('');
    });

    it('có gợi ý cho answer rỗng (nói rõ 2 khả năng + cách kiểm tra)', () => {
        expect(EMPTY_ANSWER_HINT).toContain('câu hỏi');
        expect(EMPTY_ANSWER_HINT).toContain('Kho tài liệu');
    });
});
