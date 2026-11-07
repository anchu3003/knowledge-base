'use client';

import {ShieldAlert} from 'lucide-react';

interface PiiBadgeProps {
    count: number;
}

/**
 * Icon-only badge + tooltip cho biết đã che PII trước khi gửi LLM (KB-1.3).
 * Hiển thị khi count > 0. Tooltip (title) hiện TỔNG số chỗ đã che.
 */
export function PiiBadge({count}: PiiBadgeProps) {
    if (!count || count <= 0) return null;
    const label = `Đã che ${count} thông tin nhạy cảm (PII) trước khi gửi tới AI`;
    return (
        <span
            role="img"
            title={label}
            aria-label={label}
            className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-amber-300 bg-amber-50 text-amber-600 transition-colors hover:bg-amber-100 dark:border-amber-700/50 dark:bg-amber-900/20 dark:text-amber-300"
        >
            <ShieldAlert className="h-3.5 w-3.5"/>
        </span>
    );
}
