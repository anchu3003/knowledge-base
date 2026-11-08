'use client';

import * as React from 'react';
import * as SheetPrimitive from '@radix-ui/react-dialog';
import {XIcon} from 'lucide-react';

import {cn} from '@/lib/utils';

/**
 * Sheet = drawer dựng trên Radix **Dialog** (KB-4.8).
 *
 * Lý do dùng: overlay tự viết (`<div role="dialog">` trong `documents-panel.tsx` bản cũ) thiếu
 * focus trap, `aria-modal`, khoá scroll body, và ESC chỉ hoạt động nhờ `useEffect` thủ công.
 * Radix Dialog cho tất cả miễn phí — **không thêm dependency** vì `@radix-ui/react-dialog` đã cài.
 */
function Sheet(props: React.ComponentProps<typeof SheetPrimitive.Root>) {
    return <SheetPrimitive.Root data-slot="sheet" {...props}/>;
}

function SheetTrigger(props: React.ComponentProps<typeof SheetPrimitive.Trigger>) {
    return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props}/>;
}

function SheetClose(props: React.ComponentProps<typeof SheetPrimitive.Close>) {
    return <SheetPrimitive.Close data-slot="sheet-close" {...props}/>;
}

function SheetOverlay({className, ...props}: React.ComponentProps<typeof SheetPrimitive.Overlay>) {
    return (
        <SheetPrimitive.Overlay
            data-slot="sheet-overlay"
            className={cn(
                'fixed inset-0 z-50 bg-black/50 backdrop-blur-[2px]',
                'data-[state=open]:animate-in data-[state=open]:fade-in-0',
                'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
                className,
            )}
            {...props}
        />
    );
}

/** `side` = phía trượt vào; drawer Kho tài liệu dùng `right`, menu mobile dùng `left`. */
function SheetContent({
                          className,
                          children,
                          side = 'right',
                          showCloseButton = true,
                          ...props
                      }: React.ComponentProps<typeof SheetPrimitive.Content> & {
    side?: 'top' | 'right' | 'bottom' | 'left';
    showCloseButton?: boolean;
}) {
    return (
        <SheetPrimitive.Portal>
            <SheetOverlay/>
            <SheetPrimitive.Content
                data-slot="sheet-content"
                className={cn(
                    'fixed z-50 flex flex-col gap-4 bg-background shadow-lg transition ease-in-out',
                    'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:duration-200 data-[state=open]:duration-300',
                    side === 'right' &&
                    'inset-y-0 right-0 h-full w-full border-l sm:max-w-md data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right',
                    side === 'left' &&
                    'inset-y-0 left-0 h-full w-72 border-r data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left',
                    side === 'top' && 'inset-x-0 top-0 h-auto border-b data-[state=open]:slide-in-from-top data-[state=closed]:slide-out-to-top',
                    side === 'bottom' &&
                    'inset-x-0 bottom-0 h-auto border-t data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom',
                    className,
                )}
                {...props}
            >
                {children}
                {showCloseButton && (
                    <SheetPrimitive.Close
                        data-slot="sheet-close-button"
                        className="absolute top-3 right-3 rounded-sm p-1 opacity-70 transition-opacity hover:opacity-100 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                    >
                        <XIcon className="size-4"/>
                        <span className="sr-only">Đóng</span>
                    </SheetPrimitive.Close>
                )}
            </SheetPrimitive.Content>
        </SheetPrimitive.Portal>
    );
}

function SheetHeader({className, ...props}: React.ComponentProps<'div'>) {
    return <div data-slot="sheet-header" className={cn('flex flex-col gap-1 p-4 pr-10', className)} {...props}/>;
}

function SheetFooter({className, ...props}: React.ComponentProps<'div'>) {
    return <div data-slot="sheet-footer" className={cn('mt-auto flex flex-col gap-2 p-4', className)} {...props}/>;
}

function SheetTitle({className, ...props}: React.ComponentProps<typeof SheetPrimitive.Title>) {
    return (
        <SheetPrimitive.Title
            data-slot="sheet-title"
            className={cn('text-base font-semibold text-foreground', className)}
            {...props}
        />
    );
}

function SheetDescription({className, ...props}: React.ComponentProps<typeof SheetPrimitive.Description>) {
    return (
        <SheetPrimitive.Description
            data-slot="sheet-description"
            className={cn('text-sm text-muted-foreground', className)}
            {...props}
        />
    );
}

export {
    Sheet,
    SheetTrigger,
    SheetClose,
    SheetContent,
    SheetHeader,
    SheetFooter,
    SheetTitle,
    SheetDescription,
};
