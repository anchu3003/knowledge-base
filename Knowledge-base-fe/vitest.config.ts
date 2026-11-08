import {defineConfig} from 'vitest/config';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));

/**
 * Vitest cho FE (KB-4.6) — jsdom + alias `@/` giống tsconfig.
 * Test nằm trong `tests/`, **không** gọi mạng (mock `fetch` bằng `vi.stubGlobal`).
 */
export default defineConfig({
    esbuild: {jsx: 'automatic'},
    resolve: {
        alias: {
            '@': root,
        },
    },
    test: {
        environment: 'jsdom',
        // jsdom cần origin thật để có `window.localStorage` (KB-4.8: tái hiện lựa chọn theme).
        // Không set ⇒ origin `about:blank` (opaque) ⇒ `window.localStorage === undefined`.
        environmentOptions: {jsdom: {url: 'http://localhost:3000'}},
        globals: true,
        setupFiles: ['./tests/setup.ts'],
        include: ['tests/**/*.test.{ts,tsx}'],
        testTimeout: 5000,
        restoreMocks: true,
    },
});
