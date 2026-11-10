/**
 * Tuỳ chỉnh tham số trả lời (KB-9.2) — `max_tokens` + `temperature` gửi kèm mỗi request `/chat`.
 *
 * Vì sao có file này: UI **đã** có 2 control (trong panel "tuỳ chọn" của composer) nhưng default bị
 * hard-code `1000 / 0.7` và **không lưu** ⇒ F5 là mất, và người dùng luôn chạy đúng 2 con số đó dù BE đã
 * có default tốt hơn (`DEFAULT_MAX_TOKENS=2500` / `DEFAULT_TEMPERATURE=0.2` từ KB-9.1).
 *
 * Quy ước: `null` = **"theo server"** (không gửi field ⇒ BE dùng env). Nhờ vậy đổi default ở BE là FE
 * hưởng ngay, không phải sửa code FE.
 *
 * Cùng pattern với `chat-store.ts` (ADR-0015): store ngoài React + `useSyncExternalStore`, snapshot rỗng
 * cho SSR ⇒ không lệch hydration khi đọc `localStorage`.
 */

export const ANSWER_SETTINGS_KEY = 'kb.answer.v1';

/** Giới hạn phải khớp `ChatRequest` ở BE (`ge=64, le=8000`, temperature `0..2`). */
export const MAX_TOKENS_MIN = 200;
export const MAX_TOKENS_MAX = 4000;
export const TEMPERATURE_MIN = 0;
export const TEMPERATURE_MAX = 1;

export interface AnswerSettings {
    /** `null` ⇒ theo server (`DEFAULT_MAX_TOKENS`). */
    maxTokens: number | null;
    /** `null` ⇒ theo server (`DEFAULT_TEMPERATURE`). */
    temperature: number | null;
}

export const SERVER_DEFAULT_ANSWER_SETTINGS: AnswerSettings = {maxTokens: null, temperature: null};

/** Snapshot ổn định cho SSR (cùng tham chiếu ⇒ `useSyncExternalStore` không loop). */
const SERVER_SNAPSHOT: AnswerSettings = SERVER_DEFAULT_ANSWER_SETTINGS;

let state: AnswerSettings = SERVER_DEFAULT_ANSWER_SETTINGS;
const listeners = new Set<() => void>();

function emit(): void {
    for (const listener of listeners) listener();
}

function clampNumber(value: unknown, min: number, max: number): number | null {
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n)) return null;
    return Math.min(max, Math.max(min, Math.round(n * 100) / 100));
}

/** Chuẩn hoá dữ liệu bất kỳ (từ `localStorage` hoặc từ UI) thành settings hợp lệ. */
export function normalizeAnswerSettings(raw: unknown): AnswerSettings {
    if (!raw || typeof raw !== 'object') return {...SERVER_DEFAULT_ANSWER_SETTINGS};
    const source = raw as Record<string, unknown>;
    const maxTokens = source.maxTokens === null || source.maxTokens === undefined
        ? null
        : clampNumber(source.maxTokens, MAX_TOKENS_MIN, MAX_TOKENS_MAX);
    const temperature = source.temperature === null || source.temperature === undefined
        ? null
        : clampNumber(source.temperature, TEMPERATURE_MIN, TEMPERATURE_MAX);
    return {
        maxTokens: maxTokens === null ? null : Math.round(maxTokens),
        temperature,
    };
}

/** Parse `localStorage` — JSON hỏng/không tồn tại ⇒ về "theo server" (không bao giờ throw). */
export function parseAnswerSettings(raw: string | null): AnswerSettings {
    if (!raw) return {...SERVER_DEFAULT_ANSWER_SETTINGS};
    try {
        return normalizeAnswerSettings(JSON.parse(raw));
    } catch {
        return {...SERVER_DEFAULT_ANSWER_SETTINGS};
    }
}

export function serializeAnswerSettings(settings: AnswerSettings): string {
    return JSON.stringify(normalizeAnswerSettings(settings));
}

// ------------------------------
// Store plumbing (dùng cho `useSyncExternalStore`)
// ------------------------------
export function getAnswerSettingsSnapshot(): AnswerSettings {
    return state;
}

export function getAnswerSettingsServerSnapshot(): AnswerSettings {
    return SERVER_SNAPSHOT;
}

export function subscribeAnswerSettings(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
}

/** Áp settings mới (đã chuẩn hoá) + ghi `localStorage`. Gọi trong event handler. */
export function setAnswerSettings(next: AnswerSettings): AnswerSettings {
    const normalized = normalizeAnswerSettings(next);
    state = normalized;
    try {
        window.localStorage.setItem(ANSWER_SETTINGS_KEY, serializeAnswerSettings(normalized));
    } catch {
        // private mode / quota: giữ trong RAM, không làm hỏng chat
    }
    emit();
    return normalized;
}

/** Đọc từ `localStorage` (gọi 1 lần sau khi mount). Không có gì ⇒ giữ "theo server". */
export function hydrateAnswerSettings(): AnswerSettings {
    let raw: string | null = null;
    try {
        raw = window.localStorage.getItem(ANSWER_SETTINGS_KEY);
    } catch {
        raw = null;
    }
    state = parseAnswerSettings(raw);
    emit();
    return state;
}

/** Chỉ dùng cho test: đưa store về trạng thái ban đầu. */
export function resetAnswerSettingsForTests(): void {
    state = SERVER_DEFAULT_ANSWER_SETTINGS;
    listeners.clear();
}
