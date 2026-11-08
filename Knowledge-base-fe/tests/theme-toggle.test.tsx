import {beforeEach, describe, expect, it} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import {ThemeToggle} from '@/components/theme-toggle';
import {TooltipProvider} from '@/components/ui/tooltip';
import {THEME_STORAGE_KEY} from '@/lib/theme';

/** Tooltip của Radix cần Provider (giống `AppProviders` trong app thật). */
function renderToggle() {
    return render(
        <TooltipProvider>
            <ThemeToggle/>
        </TooltipProvider>,
    );
}

describe('ThemeToggle (KB-4.8)', () => {
    beforeEach(() => {
        window.localStorage.clear();
        document.documentElement.classList.remove('dark');
    });

    it('mặc định "Theo hệ thống" khi chưa có lựa chọn nào', () => {
        renderToggle();
        expect(screen.getByRole('button', {name: /Giao diện: Theo hệ thống/})).toBeInTheDocument();
    });

    it('bấm lần 1 (system → light): bỏ .dark, lưu localStorage', async () => {
        const user = userEvent.setup();
        renderToggle();

        await user.click(screen.getByRole('button', {name: /Giao diện/}));

        expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
        expect(document.documentElement.classList.contains('dark')).toBe(false);
        expect(screen.getByRole('button', {name: /Giao diện: Sáng/})).toBeInTheDocument();
    });

    it('bấm lần 2 (light → dark): gắn .dark + color-scheme=dark', async () => {
        const user = userEvent.setup();
        renderToggle();

        const button = screen.getByRole('button', {name: /Giao diện/});
        await user.click(button); // → light
        await user.click(button); // → dark

        expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
        expect(document.documentElement.classList.contains('dark')).toBe(true);
        expect(document.documentElement.style.colorScheme).toBe('dark');
        expect(screen.getByRole('button', {name: /Giao diện: Tối/})).toBeInTheDocument();
    });

    it('giữ lựa chọn sau reload: localStorage=dark ⇒ lần mount sau vẫn dark', async () => {
        window.localStorage.setItem(THEME_STORAGE_KEY, 'dark');
        renderToggle();

        expect(screen.getByRole('button', {name: /Giao diện: Tối/})).toBeInTheDocument();
        expect(document.documentElement.classList.contains('dark')).toBe(true);
    });

    it('vòng xoay đủ 3 bước rồi quay lại system', async () => {
        const user = userEvent.setup();
        renderToggle();

        const button = screen.getByRole('button', {name: /Giao diện/});
        await user.click(button); // light
        await user.click(button); // dark
        await user.click(button); // system

        expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('system');
        expect(screen.getByRole('button', {name: /Giao diện: Theo hệ thống/})).toBeInTheDocument();
    });
});
