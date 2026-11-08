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
        globals: true,
        setupFiles: ['./tests/setup.ts'],
        include: ['tests/**/*.test.{ts,tsx}'],
        testTimeout: 5000,
        restoreMocks: true,
    },
});
