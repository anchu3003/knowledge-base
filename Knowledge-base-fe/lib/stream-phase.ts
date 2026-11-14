/**
 * Pha của một lượt hỏi–đáp khi stream (KB-4.11) — **hàm thuần**, không phụ thuộc React.
 *
 * Vì sao cần: đo thật cho thấy event `start` của BE đến sau **~12,9s** (rerank CPU ~12,8s — TD-15),
 * nên nếu UI chỉ có một spinner câm thì người dùng tưởng treo. Tách 2 pha:
 *   `retrieving` = đã gửi, **chưa** có `start` (đang truy hồi + rerank)
 *   `writing`    = đã có `start`, đang nhận token
 */

export type StreamPhase = 'idle' | 'retrieving' | 'writing' | 'done' | 'empty';

export interface StreamPhaseInput {
    /** Request đang chạy (từ lúc bấm gửi tới lúc `end`/lỗi/Stop). */
    loading: boolean;
    /** Đã nhận event `start` từ BE ⇒ BE đã truy hồi xong, bắt đầu sinh chữ. */
    started: boolean;
    /** Đã nhận `end` (hoặc lỗi / người dùng Stop). */
    finished: boolean;
    /** `end.answer` rỗng/whitespace ⇒ model không trả lời (KB-4.11). */
    answerEmpty?: boolean;
}

/**
 * Pha hiện tại. Thứ tự ưu tiên: `finished` → `loading` + `started` → `loading` → `idle`.
 * `answerEmpty` chỉ có ý nghĩa khi đã `finished` (tránh báo "rỗng" khi còn đang stream).
 */
export function phaseOf({loading, started, finished, answerEmpty}: StreamPhaseInput): StreamPhase {
    if (finished) return answerEmpty ? 'empty' : 'done';
    if (!loading) return 'idle';
    return started ? 'writing' : 'retrieving';
}

/** Nhãn tiếng Việt cho từng pha (rỗng với `idle`/`done` — không cần hiện gì). */
export function phaseLabel(phase: StreamPhase): string {
    switch (phase) {
        case 'retrieving':
            return 'Đang truy hồi tài liệu…';
        case 'writing':
            return 'Đang viết câu trả lời…';
        case 'empty':
            return 'Model không trả về nội dung';
        default:
            return '';
    }
}

/** Gợi ý khi answer rỗng — hiện dưới nhãn (KB-4.11). */
export const EMPTY_ANSWER_HINT =
    'Có thể câu hỏi quá ngắn / không khớp tài liệu, hoặc kho tài liệu chưa có nội dung liên quan. ' +
    'Thử hỏi cụ thể hơn, hoặc mở Kho tài liệu để kiểm tra số chunk đã index.';

/** `ms` → chuỗi giây đã trôi (làm tròn xuống, không âm). */
export function formatSeconds(ms: number): string {
    const seconds = Math.max(0, Math.floor(ms / 1000));
    return `${seconds}s`;
}

/** Nhãn kèm thời gian đã chờ, ví dụ `Đang truy hồi tài liệu… (7s)`. */
export function phaseLabelWithElapsed(phase: StreamPhase, elapsedMs: number): string {
    const label = phaseLabel(phase);
    if (!label) return '';
    return `${label} (${formatSeconds(elapsedMs)})`;
}
