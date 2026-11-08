'use client';

import {createContext, useCallback, useContext, useEffect, useMemo, useRef, useState} from 'react';
import {
    Toast,
    ToastClose,
    ToastDescription,
    ToastProvider as RadixToastProvider,
    ToastTitle,
    ToastViewport,
} from '@/components/ui/toast';

/**
 * Toast store tối giản (KB-4.8) — **không thêm dep** (Radix Toast đã cài).
 *
 * Dùng cho feedback ngắn ("Đã copy câu trả lời") thay vì `alert()` hay state rải rác ở từng component.
 * Không cần hàng đợi phức tạp: mỗi toast tự đóng sau `duration` (mặc định 3s) hoặc bấm X.
 */

export type ToastVariant = 'default' | 'destructive';

export interface ToastOptions {
    title: string;
    description?: string;
    variant?: ToastVariant;
    /** ms — mặc định 3000ms. */
    duration?: number;
}

interface ToastItem extends ToastOptions {
    id: number;
}

interface ToastContextValue {
    toast: (options: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const DEFAULT_DURATION = 3000;

/** Một toast — tự đóng bằng `setTimeout` (cleanup khi unmount hoặc bị đóng tay). */
function ToastRow({item, onDismiss}: {item: ToastItem; onDismiss: (id: number) => void}) {
    useEffect(() => {
        const timer = setTimeout(() => onDismiss(item.id), item.duration ?? DEFAULT_DURATION);
        return () => clearTimeout(timer);
    }, [item.id, item.duration, onDismiss]);

    return (
        <Toast
            open
            onOpenChange={(open) => {
                if (!open) onDismiss(item.id);
            }}
            data-variant={item.variant ?? 'default'}
            className={item.variant === 'destructive' ? 'border-destructive/50' : undefined}
        >
            <div className="flex flex-col gap-1">
                <ToastTitle>{item.title}</ToastTitle>
                {item.description && <ToastDescription>{item.description}</ToastDescription>}
            </div>
            <ToastClose/>
        </Toast>
    );
}

/**
 * Bọc `children` + render viewport. Đặt **một lần** ở `app/layout.tsx`
 * (`AppProviders`) để mọi component client dùng được `useToast()`.
 */
export function ToastProvider({children}: {children: React.ReactNode}) {
    const [items, setItems] = useState<ToastItem[]>([]);
    const nextId = useRef(1);

    const dismiss = useCallback((id: number) => {
        setItems((prev) => prev.filter((item) => item.id !== id));
    }, []);

    const toast = useCallback((options: ToastOptions) => {
        const id = nextId.current++;
        // Giữ tối đa 3 toast để không che nội dung chat
        setItems((prev) => [...prev.slice(-2), {...options, id}]);
    }, []);

    const value = useMemo<ToastContextValue>(() => ({toast}), [toast]);

    return (
        <ToastContext.Provider value={value}>
            <RadixToastProvider swipeDirection="right">
                {children}
                {items.map((item) => (
                    <ToastRow key={item.id} item={item} onDismiss={dismiss}/>
                ))}
                <ToastViewport/>
            </RadixToastProvider>
        </ToastContext.Provider>
    );
}

/**
 * Hook lấy `toast()`. Nếu component nằm ngoài provider (test render riêng lẻ) ⇒ trả về hàm no-op
 * thay vì throw, để test component đơn lẻ không phải bọc provider.
 */
export function useToast(): ToastContextValue {
    const context = useContext(ToastContext);
    return context ?? {toast: () => undefined};
}
