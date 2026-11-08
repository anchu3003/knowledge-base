'use client';

import {TooltipProvider} from '@/components/ui/tooltip';
import {ToastProvider} from '@/components/toast-provider';

/**
 * Provider dùng chung cho toàn app (KB-4.8).
 *
 * Phải là client component để `app/layout.tsx` giữ được server component.
 * Đặt ở đây thay vì từng trang để mọi route đều có tooltip + toast.
 */
export function AppProviders({children}: {children: React.ReactNode}) {
    return (
        <TooltipProvider>
            <ToastProvider>{children}</ToastProvider>
        </TooltipProvider>
    );
}
