'use client';

/**
 * Màn hình nhập token khi bật auth (KB-5.5 — **mặc định TẮT**).
 *
 * Vì sao cần: khi `NEXT_PUBLIC_AUTH_ENABLED=true`, BE chặn mọi endpoint trừ `/health` ⇒ nếu không có token thì
 * app chỉ hiện banner lỗi 401. Thay vì bắt người dùng mở DevTools, hiện 1 form 1 ô (không phải login form đầy đủ —
 * không user/role, YAGNI theo Q&A KB-5.5).
 *
 * Token lưu ở `localStorage` (runtime) — **không** nhúng vào bundle vì `NEXT_PUBLIC_*` là công khai.
 */

import {useState} from 'react';
import {KeyRound} from 'lucide-react';

import {AUTH_ENABLED, readApiToken, saveApiToken} from '@/lib/api';
import {Button} from '@/components/ui/button';

export function TokenGate({children}: {children: React.ReactNode}) {
    // Cờ tắt (mặc định) ⇒ không làm gì cả, app chạy như trước KB-5.5.
    const [token, setToken] = useState<string | null>(() => (AUTH_ENABLED ? readApiToken() : 'dummy'));
    const [input, setInput] = useState('');
    const [error, setError] = useState<string | null>(null);

    if (!AUTH_ENABLED || token) return <>{children}</>;

    const handleSubmit = (event: React.FormEvent) => {
        event.preventDefault();
        if (!input.trim()) {
            setError('Token không được để trống.');
            return;
        }
        saveApiToken(input);
        setToken(input.trim());
        setError(null);
    };

    return (
        <div className="flex min-h-svh items-center justify-center bg-background px-4">
            <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 rounded-2xl bg-card p-6 shadow-sm">
                <div className="flex items-center gap-2">
                    <KeyRound className="size-4 text-primary"/>
                    <h1 className="text-sm font-semibold text-foreground">Cần API token</h1>
                </div>
                <p className="text-xs text-muted-foreground">
                    Kho tài liệu này đang bật auth. Nhập token cấu hình ở backend (<code>API_TOKEN</code>) để tiếp tục.
                </p>
                <input
                    type="password"
                    autoFocus
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    aria-label="API token"
                    placeholder="API token"
                    className="w-full rounded-lg bg-muted/40 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                />
                {error && <p className="text-xs text-destructive">{error}</p>}
                <Button type="submit" className="w-full">Lưu token</Button>
                <p className="text-[11px] text-muted-foreground">
                    Token chỉ lưu trong trình duyệt này (<code>localStorage</code>), không gửi đi đâu ngoài backend của bạn.
                </p>
            </form>
        </div>
    );
}

/** Đăng xuất = xoá token khỏi trình duyệt rồi tải lại (dùng ở header khi bật auth). */
export function clearTokenAndReload(): void {
    saveApiToken('');
    if (typeof window !== 'undefined') window.location.reload();
}
