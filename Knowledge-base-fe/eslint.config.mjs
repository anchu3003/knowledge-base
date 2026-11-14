import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';

/**
 * ESLint flat config (Next 16 dùng flat config, `next lint` đã bị bỏ) — KB-4.6.
 * `npm run lint` = `eslint .`; build cũng type-check thật (`ignoreBuildErrors: false`).
 */
const config = [
    {
        ignores: ['.next/**', 'node_modules/**', 'next-env.d.ts', 'vitest.config.ts'],
    },
    ...nextCoreWebVitals,
    ...nextTypescript,
    {
        rules: {
            // Comment/JSX trong repo viết tiếng Việt, dấu nháy đôi là chủ ý
            'react/no-unescaped-entities': 'off',
            '@typescript-eslint/no-explicit-any': 'warn',
            '@typescript-eslint/no-unused-vars': ['warn', {argsIgnorePattern: '^_', varsIgnorePattern: '^_'}],
            // KB-4.6: 3 chỗ cố ý setState trong effect — đọc `localStorage` sau mount (SSR/hydration) và
            // fetch khi mở drawer. Rule mới của react-hooks không có cách sửa sạch cho 2 ca này, hạ xuống warn.
            'react-hooks/set-state-in-effect': 'warn',
        },
    },
];

export default config;
