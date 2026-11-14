/**
 * KB-9.2: tuỳ chỉnh `max_tokens`/`temperature` (null = theo server) — clamp, parse, persist.
 */
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {
    ANSWER_SETTINGS_KEY,
    MAX_TOKENS_MAX,
    MAX_TOKENS_MIN,
    SERVER_DEFAULT_ANSWER_SETTINGS,
    TEMPERATURE_MAX,
    getAnswerSettingsSnapshot,
    hydrateAnswerSettings,
    normalizeAnswerSettings,
    parseAnswerSettings,
    resetAnswerSettingsForTests,
    serializeAnswerSettings,
    setAnswerSettings,
    subscribeAnswerSettings,
} from '@/lib/answer-settings';

describe('answer-settings (KB-9.2)', () => {
    beforeEach(() => {
        resetAnswerSettingsForTests();
        window.localStorage.clear();
    });

    it('mặc định = "theo server" (null cả 2) ⇒ FE không gửi field, BE dùng env', () => {
        expect(getAnswerSettingsSnapshot()).toEqual(SERVER_DEFAULT_ANSWER_SETTINGS);
        expect(parseAnswerSettings(null)).toEqual(SERVER_DEFAULT_ANSWER_SETTINGS);
    });

    it('clamp max tokens vào [min, max] và temperature vào [0, 1]', () => {
        expect(normalizeAnswerSettings({maxTokens: 1, temperature: 5}))
            .toEqual({maxTokens: MAX_TOKENS_MIN, temperature: TEMPERATURE_MAX});
        expect(normalizeAnswerSettings({maxTokens: 99999, temperature: -1}))
            .toEqual({maxTokens: MAX_TOKENS_MAX, temperature: 0});
    });

    it('temperature = 0 vẫn giữ 0 (không bị coi là "chưa set")', () => {
        const settings = setAnswerSettings({maxTokens: 2500, temperature: 0});
        expect(settings.temperature).toBe(0);
        expect(getAnswerSettingsSnapshot().temperature).toBe(0);
    });

    it('JSON hỏng trong localStorage ⇒ về "theo server", không throw', () => {
        expect(parseAnswerSettings('{not json')).toEqual(SERVER_DEFAULT_ANSWER_SETTINGS);
        expect(parseAnswerSettings('"abc"')).toEqual(SERVER_DEFAULT_ANSWER_SETTINGS);
    });

    it('setAnswerSettings ghi localStorage + notify subscriber', () => {
        const listener = vi.fn();
        const unsubscribe = subscribeAnswerSettings(listener);

        setAnswerSettings({maxTokens: 3000, temperature: 0.1});

        expect(listener).toHaveBeenCalledTimes(1);
        expect(JSON.parse(window.localStorage.getItem(ANSWER_SETTINGS_KEY) || '{}'))
            .toEqual({maxTokens: 3000, temperature: 0.1});
        unsubscribe();
    });

    it('hydrate đọc lại giá trị đã lưu; không có gì thì giữ "theo server"', () => {
        window.localStorage.setItem(ANSWER_SETTINGS_KEY, serializeAnswerSettings({maxTokens: 1200, temperature: 0.9}));
        expect(hydrateAnswerSettings()).toEqual({maxTokens: 1200, temperature: 0.9});

        window.localStorage.clear();
        expect(hydrateAnswerSettings()).toEqual(SERVER_DEFAULT_ANSWER_SETTINGS);
    });

    it('null từ localStorage (người dùng bấm "Dùng theo server" lần trước) vẫn là null', () => {
        window.localStorage.setItem(ANSWER_SETTINGS_KEY, JSON.stringify({maxTokens: null, temperature: null}));
        expect(hydrateAnswerSettings()).toEqual(SERVER_DEFAULT_ANSWER_SETTINGS);
    });
});
