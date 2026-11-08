'use client';

import {useEffect, useState, useSyncExternalStore} from 'react';
import {Monitor, Moon, Sun} from 'lucide-react';

import {Button} from '@/components/ui/button';
import {Tooltip, TooltipContent, TooltipTrigger} from '@/components/ui/tooltip';
import {
    THEME_STORAGE_KEY,
    applyThemeToDocument,
    getThemeServerSnapshot,
    getThemeSnapshot,
    nextThemeMode,
    subscribeThemeNoop,
    themeModeLabel,
    type ThemeMode,
} from '@/lib/theme';

/**
 * Nút chuyển theme (KB-4.8): **Sáng → Tối → Theo hệ thống**, lưu ở `localStorage`.
 *
 * Đọc localStorage bằng `useSyncExternalStore` (external store) thay vì `useState` + `setState` trong
 * effect: (1) không bị rule `react-hooks/set-state-in-effect` chặn, (2) SSR dùng snapshot `system` nên
 * markup server/khớp client, không lệch hydration.
 *
 * Không dùng `next-themes` (Q&A KB-4.8 giả định (b)) ⇒ không thêm dep.
 */
export function ThemeToggle() {
    const storedMode = useSyncExternalStore(subscribeThemeNoop, getThemeSnapshot, getThemeServerSnapshot);
    // `override` = mode người dùng vừa chọn trong session này (chưa kịp là snapshot mới của localStorage)
    const [override, setOverride] = useState<ThemeMode | null>(null);
    const mode = override ?? storedMode;

    useEffect(() => {
        const media = window.matchMedia('(prefers-color-scheme: dark)');

        // Áp ngay + theo dõi OS đổi theme để chế độ `system` cập nhật không cần reload
        const apply = () => applyThemeToDocument(mode, media.matches);
        apply();
        media.addEventListener('change', apply);

        try {
            window.localStorage.setItem(THEME_STORAGE_KEY, mode);
        } catch {
            // localStorage bị chặn (private mode) — theme vẫn áp dụng cho session hiện tại
        }

        return () => media.removeEventListener('change', apply);
    }, [mode]);

    const upcoming = nextThemeMode(mode);
    const label = themeModeLabel(mode);
    const Icon = mode === 'light' ? Sun : mode === 'dark' ? Moon : Monitor;

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => setOverride(upcoming)}
                    aria-label={`Giao diện: ${label} — bấm để chuyển sang ${themeModeLabel(upcoming)}`}
                    data-theme-mode={mode}
                >
                    <Icon className="size-4"/>
                </Button>
            </TooltipTrigger>
            <TooltipContent>
                Giao diện: {label} → {themeModeLabel(upcoming)}
            </TooltipContent>
        </Tooltip>
    );
}
