'use client';

import * as React from 'react';
import * as ToastPrimitive from '@radix-ui/react-toast';
import {XIcon} from 'lucide-react';

import {cn} from '@/lib/utils';

/**
 * Toast shadcn (KB-4.8) — wrapper Radix Toast (đã có trong dependencies).
 * Dùng qua `useToast()` trong `components/toast-provider.tsx`; không gọi trực tiếp primitive.
 */
function ToastProvider(props: React.ComponentProps<typeof ToastPrimitive.Provider>) {
    return <ToastPrimitive.Provider {...props}/>;
}

function ToastViewport({className, ...props}: React.ComponentProps<typeof ToastPrimitive.Viewport>) {
    return (
        <ToastPrimitive.Viewport
            data-slot="toast-viewport"
            className={cn(
                'fixed bottom-4 right-4 z-100 flex max-h-screen w-full max-w-sm flex-col gap-2 outline-none',
                className,
            )}
            {...props}
        />
    );
}

function Toast({className, ...props}: React.ComponentProps<typeof ToastPrimitive.Root>) {
    return (
        <ToastPrimitive.Root
            data-slot="toast"
            className={cn(
                'group pointer-events-auto relative flex w-full items-start gap-3 overflow-hidden rounded-lg border bg-background p-3 pr-8 shadow-lg',
                'data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom-2 data-[state=open]:fade-in-0',
                'data-[state=closed]:animate-out data-[state=closed]:fade-out-80',
                'data-[swipe=end]:animate-out',
                className,
            )}
            {...props}
        />
    );
}

function ToastTitle({className, ...props}: React.ComponentProps<typeof ToastPrimitive.Title>) {
    return <ToastPrimitive.Title data-slot="toast-title" className={cn('text-sm font-medium', className)} {...props}/>;
}

function ToastDescription({className, ...props}: React.ComponentProps<typeof ToastPrimitive.Description>) {
    return (
        <ToastPrimitive.Description
            data-slot="toast-description"
            className={cn('text-xs text-muted-foreground', className)}
            {...props}
        />
    );
}

function ToastClose({className, ...props}: React.ComponentProps<typeof ToastPrimitive.Close>) {
    return (
        <ToastPrimitive.Close
            data-slot="toast-close"
            aria-label="Đóng thông báo"
            className={cn(
                'absolute top-2 right-2 rounded-sm p-0.5 text-muted-foreground opacity-70 transition-opacity hover:opacity-100',
                className,
            )}
            {...props}
        >
            <XIcon className="size-3.5"/>
        </ToastPrimitive.Close>
    );
}

export {ToastProvider, ToastViewport, Toast, ToastTitle, ToastDescription, ToastClose};
