import {describe, expect, it, vi} from 'vitest';
import {
    DEFAULT_THEME_MODE,
    THEME_INIT_SCRIPT,
    THEME_STORAGE_KEY,
    applyThemeToDocument,
    getThemeServerSnapshot,
    getThemeSnapshot,
    isThemeMode,
    nextThemeMode,
    readStoredTheme,
    resolveTheme,
    themeModeLabel,
} from '@/lib/theme';

/** Storage giả — chỉ cần `getItem` (theme không tự ghi trong lib). */
function fakeStorage(value: string | null) {
    return {getItem: vi.fn(() => value)};
}

describe('theme (KB-4.8)', () => {
    it('giá trị hợp lệ chỉ là light/dark/system', () => {
        expect(isThemeMode('light')).toBe(true);
        expect(isThemeMode('dark')).toBe(true);
        expect(isThemeMode('system')).toBe(true);
        expect(isThemeMode('Dark')).toBe(false);
        expect(isThemeMode(null)).toBe(false);
        expect(isThemeMode('')).toBe(false);
    });

    it('đọc localStorage: giá trị lạ ⇒ fallback system', () => {
        expect(readStoredTheme(fakeStorage('dark'))).toBe('dark');
        expect(readStoredTheme(fakeStorage('neon'))).toBe('system');
        expect(readStoredTheme(fakeStorage(null))).toBe('system');
        expect(readStoredTheme(null)).toBe(DEFAULT_THEME_MODE);
    });

    it('localStorage bị chặn (private mode) ⇒ fallback, không throw', () => {
        const throwing = {
            getItem: () => {
                throw new Error('SecurityError');
            },
        };
        expect(() => readStoredTheme(throwing)).not.toThrow();
        expect(readStoredTheme(throwing)).toBe('system');
    });

    it('resolveTheme: system theo prefers-color-scheme, light/dark giữ nguyên', () => {
        expect(resolveTheme('system', true)).toBe('dark');
        expect(resolveTheme('system', false)).toBe('light');
        expect(resolveTheme('dark', false)).toBe('dark');
        expect(resolveTheme('light', true)).toBe('light');
    });

    it('vòng xoay toggle: light → dark → system → light', () => {
        expect(nextThemeMode('light')).toBe('dark');
        expect(nextThemeMode('dark')).toBe('system');
        expect(nextThemeMode('system')).toBe('light');
    });

    it('nhãn tiếng Việt cho từng mode', () => {
        expect(themeModeLabel('light')).toBe('Sáng');
        expect(themeModeLabel('dark')).toBe('Tối');
        expect(themeModeLabel('system')).toBe('Theo hệ thống');
    });

    it('applyThemeToDocument gắn/bỏ class .dark + set color-scheme', () => {
        const classes = new Set<string>();
        const root = {
            classList: {
                toggle: (name: string, force?: boolean) => {
                    if (force) classes.add(name);
                    else classes.delete(name);
                    return force ?? false;
                },
            },
            style: {colorScheme: ''},
        } as unknown as Pick<HTMLElement, 'classList' | 'style'>;

        expect(applyThemeToDocument('dark', false, root)).toBe('dark');
        expect(classes.has('dark')).toBe(true);
        expect(root.style.colorScheme).toBe('dark');

        expect(applyThemeToDocument('light', true, root)).toBe('light');
        expect(classes.has('dark')).toBe(false);
        expect(root.style.colorScheme).toBe('light');
    });

    it('script chống FOUC chứa key localStorage + tên class .dark', () => {
        expect(THEME_INIT_SCRIPT).toContain(THEME_STORAGE_KEY);
        expect(THEME_INIT_SCRIPT).toContain("classList.toggle('dark'");
        expect(THEME_INIT_SCRIPT.startsWith('(function(){try{')).toBe(true);
    });

    it('snapshot: server luôn system, client đọc localStorage (jsdom)', () => {
        expect(getThemeServerSnapshot()).toBe('system');
        window.localStorage.setItem(THEME_STORAGE_KEY, 'dark');
        expect(getThemeSnapshot()).toBe('dark');
        window.localStorage.removeItem(THEME_STORAGE_KEY);
        expect(getThemeSnapshot()).toBe('system');
    });
});
