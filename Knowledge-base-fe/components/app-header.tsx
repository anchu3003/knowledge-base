'use client';

import {useState} from 'react';
import Link from 'next/link';
import {Database, Menu} from 'lucide-react';

import {ThemeToggle} from '@/components/theme-toggle';
import {Button} from '@/components/ui/button';
import {Sheet, SheetContent, SheetTitle, SheetTrigger} from '@/components/ui/sheet';
import {Tooltip, TooltipContent, TooltipTrigger} from '@/components/ui/tooltip';

interface AppHeaderProps {
    /** Mở drawer "Kho tài liệu" (KB-4.5) */
    onOpenDocuments: () => void;
    /**
     * Nội dung sidebar cho drawer mobile — render-prop để header tự đóng drawer sau khi chọn
     * (`close()`), còn state chat vẫn nằm ở `app/page.tsx`.
     */
    renderMobileSidebar?: (close: () => void) => React.ReactNode;
}

/**
 * Header (KB-4.8) — bỏ các control giả của bản onboarding: user "An Chu", badge role, nút **Logout**
 * (BE không có auth) và nút gradient tự phát. Chỉ còn: brand, drawer mobile, Kho tài liệu, theme toggle.
 */
export function AppHeader({onOpenDocuments, renderMobileSidebar}: AppHeaderProps) {
    const [sidebarOpen, setSidebarOpen] = useState(false);

    return (
        <header
            className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/85 px-3 backdrop-blur">
            {renderMobileSidebar && (
                <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
                    <SheetTrigger asChild>
                        <Button variant="ghost" size="icon-sm" className="md:hidden" aria-label="Mở menu">
                            <Menu className="size-4"/>
                        </Button>
                    </SheetTrigger>
                    <SheetContent side="left" className="w-72 p-0">
                        <SheetTitle className="sr-only">Danh sách cuộc trò chuyện</SheetTitle>
                        {renderMobileSidebar(() => setSidebarOpen(false))}
                    </SheetContent>
                </Sheet>
            )}

            <Link href="/" className="flex min-w-0 items-center gap-2">
                <span
                    className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
                    KB
                </span>
                <span className="truncate text-sm font-semibold text-foreground">Knowledge Base</span>
            </Link>

            <div className="ml-auto flex items-center gap-1">
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button variant="ghost" size="sm" onClick={onOpenDocuments} className="gap-2"
                                aria-label="Mở kho tài liệu">
                            <Database className="size-4"/>
                            <span className="hidden sm:inline">Kho tài liệu</span>
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>Trạng thái index + tài liệu đã nạp</TooltipContent>
                </Tooltip>
                <ThemeToggle/>
            </div>
        </header>
    );
}
