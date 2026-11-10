'use client';

import {useState} from 'react';
import Link from 'next/link';
import {Database, History} from 'lucide-react';

import {ThemeToggle} from '@/components/theme-toggle';
import {Badge} from '@/components/ui/badge';
import {Button} from '@/components/ui/button';
import {Sheet, SheetContent, SheetTitle, SheetTrigger} from '@/components/ui/sheet';
import {Tooltip, TooltipContent, TooltipTrigger} from '@/components/ui/tooltip';

interface AppHeaderProps {
    /** Mở drawer "Kho tài liệu" (KB-4.5) */
    onOpenDocuments: () => void;
    /**
     * Nội dung ngăn kéo lịch sử — render-prop để header tự đóng drawer sau khi chọn
     * (`close()`), còn state chat vẫn nằm ở `app/page.tsx`.
     *
     * KB-5.11: trước đây prop này chỉ dùng cho mobile (`md:hidden` hamburger); nay danh sách hội thoại
     * **chỉ** sống trong ngăn kéo nên nút hiện ở mọi kích thước.
     */
    renderSidebar?: (close: () => void) => React.ReactNode;
    /** Số cuộc trò chuyện — hiện trong `Badge` cạnh nút Lịch sử */
    sessionCount?: number;
}

/**
 * Header (KB-4.8) — bỏ các control giả của bản onboarding: user "An Chu", badge role, nút **Logout**
 * (BE không có auth) và nút gradient tự phát.
 *
 * KB-5.11: **bỏ `border-b`** (đường kẻ mờ dưới header) và đổi hamburger mobile thành nút **Lịch sử** có badge
 * số phiên — vì danh sách hội thoại không còn là cột cố định.
 */
export function AppHeader({onOpenDocuments, renderSidebar, sessionCount}: AppHeaderProps) {
    const [sidebarOpen, setSidebarOpen] = useState(false);

    return (
        <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-2 bg-background/85 px-3 backdrop-blur">
            {renderSidebar && (
                <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
                    <SheetTrigger asChild>
                        <Button variant="ghost" size="sm" className="gap-2" aria-label="Mở lịch sử trò chuyện">
                            <History className="size-4"/>
                            <span className="hidden sm:inline">Lịch sử</span>
                            {typeof sessionCount === 'number' && sessionCount > 0 && (
                                <Badge variant="muted" className="ml-0.5">{sessionCount}</Badge>
                            )}
                        </Button>
                    </SheetTrigger>
                    {/* KB-5.12: ẩn nút X mặc định — nó bị đặt absolute và đè lên nút "Cuộc trò chuyện mới".
                        Nút đóng riêng nằm trong header của ngăn kéo (app-sidebar). */}
                    <SheetContent side="left" showCloseButton={false} className="w-72 p-0">
                        <SheetTitle className="sr-only">Danh sách cuộc trò chuyện</SheetTitle>
                        {renderSidebar(() => setSidebarOpen(false))}
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

