/**
 * Test `TokenGate` (KB-5.5) — cờ **tắt** (mặc định trong test env) ⇒ không được chắn app.
 *
 * Nhánh "cần token" phụ thuộc hằng `AUTH_ENABLED` đọc từ `process.env.NEXT_PUBLIC_AUTH_ENABLED` **lúc import
 * module** (giống Next.js nhúng lúc build) ⇒ test bằng cách stub env rồi `import()` lại module.
 */

import {render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';

afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
});

describe('TokenGate (KB-5.5)', () => {
    it('cờ TẮT (mặc định) ⇒ render children, không có form token', async () => {
        vi.resetModules();
        const {TokenGate} = await import('@/components/token-gate');

        render(<TokenGate><div>nội dung app</div></TokenGate>);

        expect(screen.getByText('nội dung app')).toBeInTheDocument();
        expect(screen.queryByLabelText('API token')).not.toBeInTheDocument();
    });

    it('cờ BẬT + chưa có token ⇒ hiện form nhập token', async () => {
        vi.stubEnv('NEXT_PUBLIC_AUTH_ENABLED', 'true');
        vi.resetModules();
        window.localStorage.removeItem('kb.api_token');
        const {TokenGate} = await import('@/components/token-gate');

        render(<TokenGate><div>nội dung app</div></TokenGate>);

        expect(screen.getByLabelText('API token')).toBeInTheDocument();
        expect(screen.queryByText('nội dung app')).not.toBeInTheDocument();
    });

    it('cờ BẬT + đã có token ⇒ render children', async () => {
        vi.stubEnv('NEXT_PUBLIC_AUTH_ENABLED', 'true');
        vi.resetModules();
        window.localStorage.setItem('kb.api_token', 'token-co-san');
        const {TokenGate} = await import('@/components/token-gate');

        render(<TokenGate><div>nội dung app</div></TokenGate>);

        expect(screen.getByText('nội dung app')).toBeInTheDocument();
        window.localStorage.removeItem('kb.api_token');
    });
});
