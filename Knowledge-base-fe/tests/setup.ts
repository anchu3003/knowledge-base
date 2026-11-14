/**
 * Setup dùng chung cho vitest (KB-4.6).
 *
 * jsdom **không** có `scrollIntoView`/`clipboard` (component dùng cả hai) ⇒ stub ở đây thay vì sửa component.
 */

import '@testing-library/jest-dom/vitest';
import {afterEach, vi} from 'vitest';
import {cleanup} from '@testing-library/react';

// jsdom thiếu API layout — component gọi khi bấm chip citation (KB-4.3)
if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn();
}

// `navigator.clipboard` chỉ có trong secure context; jsdom không implement
if (!navigator.clipboard) {
    Object.defineProperty(navigator, 'clipboard', {
        value: {writeText: vi.fn().mockResolvedValue(undefined)},
        configurable: true,
    });
}

// `window.matchMedia` không có trong jsdom — `ThemeToggle` (KB-4.8) cần để resolve chế độ `system`
if (!window.matchMedia) {
    window.matchMedia = ((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
}

// `ResizeObserver` không có trong jsdom — Radix ScrollArea (sidebar KB-4.8) cần khi render item
if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
        observe() {
            // no-op
        }

        unobserve() {
            // no-op
        }

        disconnect() {
            // no-op
        }
    } as unknown as typeof ResizeObserver;
}

/**
 * jsdom 31 trong môi trường này chỉ expose `sessionStorage`, **không** có `localStorage`
 * (dù đã set `environmentOptions.jsdom.url`) ⇒ polyfill tối thiểu để test được theme + persistence.
 * Kiểm chứng: `Object.keys(window).filter(k => /storage/i.test(k))` → `['sessionStorage']`.
 */
if (!window.localStorage) {
    const store = new Map<string, string>();
    const storage: Storage = {
        get length() {
            return store.size;
        },
        key: (index: number) => Array.from(store.keys())[index] ?? null,
        getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
        setItem: (key: string, value: string) => {
            store.set(key, String(value));
        },
        removeItem: (key: string) => {
            store.delete(key);
        },
        clear: () => {
            store.clear();
        },
    };
    Object.defineProperty(window, 'localStorage', {value: storage, configurable: true});
}

afterEach(() => {
    cleanup();
});
