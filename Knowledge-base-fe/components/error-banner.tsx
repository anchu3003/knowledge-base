import {AlertTriangle, X} from 'lucide-react';

import {Button} from '@/components/ui/button';
import type {ApiErrorView} from '@/lib/errors';

interface ErrorBannerProps {
    error: ApiErrorView;
    /** Có text để gửi lại thì hiện nút "Thử lại" (KB-4.1) */
    canRetry?: boolean;
    retrying?: boolean;
    onRetry?: () => void;
    onDismiss: () => void;
}

/**
 * Banner lỗi API (KB-4.1, tách khỏi `page.tsx` ở KB-4.8).
 *
 * Hiện `message` + `hint` + `code`/`request_id` thay vì chèn message giả vào khung chat:
 * người dùng biết lỗi thuộc hệ thống hay do câu hỏi, và `request_id` dùng để tra log BE.
 */
export function ErrorBanner({error, canRetry, retrying, onRetry, onDismiss}: ErrorBannerProps) {
    return (
        <div
            role="alert"
            aria-live="assertive"
            className="border-b border-destructive/30 bg-destructive/10 px-3 py-2.5"
        >
            <div className="mx-auto flex max-w-3xl items-start gap-3">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive"/>
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-foreground">{error.message}</p>
                    {error.hint && <p className="mt-0.5 text-xs text-muted-foreground">{error.hint}</p>}
                    <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                        code: {error.code}
                        {error.requestId && error.requestId !== '-' && <span> · request_id: {error.requestId}</span>}
                    </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                    {error.retryable && canRetry && onRetry && (
                        <Button size="sm" variant="destructive" onClick={onRetry} disabled={retrying}>
                            Thử lại
                        </Button>
                    )}
                    <Button size="icon-sm" variant="ghost" onClick={onDismiss} aria-label="Đóng thông báo lỗi">
                        <X className="size-4"/>
                    </Button>
                </div>
            </div>
        </div>
    );
}
