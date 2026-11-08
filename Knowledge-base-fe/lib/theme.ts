/**
 * Theme mode (KB-4.8) — logic thuần, không phụ thuộc React ⇒ test bằng vitest.
 *
 * 3 chế độ: `light` / `dark` / `system`. `system` = theo `prefers-color-scheme` của OS.
 * Không dùng `next-themes` (Q&A KB-4.8 giả định (b)) ⇒ tự viết ~60 dòng, không thêm dep.
 *
 * Cách áp dụng: thêm/bỏ class `.dark` trên `<html>` (token trong `globals.css` đã có `.dark {}`)
 * + set `color-scheme` để scrollbar/form control của browser đổi theo.
 */

export type ThemeMode = 'light' | 'dark' | 'system';

/** Chế độ sáng/tối thực sự được áp lên DOM (sau khi resolve `system`). */
export type ResolvedTheme = 'light' | 'dark';

/** Key localStorage — có prefix `kb.` giống các key khác của app. */
export const THEME_STORAGE_KEY = 'kb.theme';

export const THEME_MODES: readonly ThemeMode[] = ['light', 'dark', 'system'];

/** Mặc định `system`: người dùng lần đầu vào app thấy đúng theme của OS. */
export const DEFAULT_THEME_MODE: ThemeMode = 'system';

export function isThemeMode(value: unknown): value is ThemeMode {
    return value === 'light' || value === 'dark' || value === 'system';
}

/**
 * Đọc mode đã lưu. Giá trị lạ (dữ liệu cũ, bị sửa tay) ⇒ fallback `system`.
 * `storage` bị chặn (private mode / SSR) ⇒ `null` ⇒ fallback, **không throw**.
 */
export function readStoredTheme(storage?: Pick<Storage, 'getItem'> | null): ThemeMode {
    if (!storage) return DEFAULT_THEME_MODE;
    try {
        const stored = storage.getItem(THEME_STORAGE_KEY);
        return isThemeMode(stored) ? stored : DEFAULT_THEME_MODE;
    } catch {
        return DEFAULT_THEME_MODE;
    }
}

/**
 * `getSnapshot` cho `useSyncExternalStore` — chỉ đọc, trả về **primitive** nên không gây re-render loop.
 * Dùng thay cho `useState` + `setState` trong effect (bị rule `react-hooks/set-state-in-effect` chặn):
 * localStorage là **external store**, đúng use case của `useSyncExternalStore`.
 */
export function getThemeSnapshot(): ThemeMode {
    if (typeof window === 'undefined') return DEFAULT_THEME_MODE;
    return readStoredTheme(window.localStorage);
}

/** Snapshot phía server: luôn `system` để HTML SSR khớp với lần render đầu trên client. */
export function getThemeServerSnapshot(): ThemeMode {
    return DEFAULT_THEME_MODE;
}

/** Không subscribe: theme chỉ đổi từ `ThemeToggle` trong app này (không nghe tab khác). */
export function subscribeThemeNoop(): () => void {
    return () => undefined;
}

/** `system` ⇒ theo OS; còn lại giữ nguyên. */
export function resolveTheme(mode: ThemeMode, prefersDark: boolean): ResolvedTheme {
    if (mode === 'system') return prefersDark ? 'dark' : 'light';
    return mode;
}

/** Vòng xoay của nút toggle: light → dark → system → light. */
export function nextThemeMode(mode: ThemeMode): ThemeMode {
    switch (mode) {
        case 'light':
            return 'dark';
        case 'dark':
            return 'system';
        default:
            return 'light';
    }
}

/** Nhãn tiếng Việt cho từng mode (dùng trong `aria-label` + tooltip). */
export function themeModeLabel(mode: ThemeMode): string {
    switch (mode) {
        case 'light':
            return 'Sáng';
        case 'dark':
            return 'Tối';
        default:
            return 'Theo hệ thống';
    }
}

/**
 * Script chạy **trước** khi React hydrate (inline trong `<head>`, xem `app/layout.tsx`).
 * Không có nó ⇒ lần load đầu bị "flash" trắng rồi mới chuyển dark (FOUC).
 * Cố tình viết ES5 + `try/catch`: chạy được cả khi localStorage bị chặn.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var m=localStorage.getItem('${THEME_STORAGE_KEY}');var d=window.matchMedia('(prefers-color-scheme: dark)').matches;var t=(m==='light'||m==='dark')?m:(d?'dark':'light');var r=document.documentElement;r.classList.toggle('dark',t==='dark');r.style.colorScheme=t;}catch(e){}})();`;

/**
 * Áp theme lên `<html>`. Tách khỏi component để test được bằng jsdom
 * (chỉ phụ thuộc `document`, không phụ thuộc React).
 */
export function applyThemeToDocument(
    mode: ThemeMode,
    prefersDark: boolean,
    root?: Pick<HTMLElement, 'classList' | 'style'> | null,
): ResolvedTheme {
    const resolved = resolveTheme(mode, prefersDark);
    const target = root ?? (typeof document === 'undefined' ? null : document.documentElement);
    if (target) {
        target.classList.toggle('dark', resolved === 'dark');
        target.style.colorScheme = resolved;
    }
    return resolved;
}
