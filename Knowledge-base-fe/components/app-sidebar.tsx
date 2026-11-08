'use client';

import {MessageSquare, Plus, Trash2} from 'lucide-react';

import {Badge} from '@/components/ui/badge';
import {Button} from '@/components/ui/button';
import {ScrollArea} from '@/components/ui/scroll-area';
import {Separator} from '@/components/ui/separator';

/**
 * Sidebar (KB-4.8) — thay `chat-history-sidebar.tsx` bản cũ (`fixed` + `ml-64` thủ công).
 *
 * 2 chỗ dùng:
 * - Desktop (≥768px): cột trái `hidden md:flex` trong `app/page.tsx`.
 * - Mobile (<768px): cùng nội dung render trong `Sheet` (drawer trượt từ trái) ở `app-header.tsx`.
 *
 * ⇒ tách `SidebarContent` (thuần props, không tự định vị) khỏi `AppSidebar` (khung cột).
 * *KB-4.9: bỏ nút "Kho tài liệu" ở đây — trùng với nút ở header (chỉ giữ 1 chỗ, góc trên phải).*
 */

export interface ChatSession {
    id: string;
    title: string;
    createdAt: Date;
    messageCount: number;
}

export interface SidebarContentProps {
    sessions: ChatSession[];
    currentSessionId?: string;
    onSelectSession: (sessionId: string) => void;
    onNewChat: () => void;
    onDeleteSession: (sessionId: string) => void;
    /** Đóng drawer mobile sau khi chọn (Sheet); desktop không truyền ⇒ no-op */
    onAfterAction?: () => void;
}

export function SidebarContent({
                                   sessions,
                                   currentSessionId,
                                   onSelectSession,
                                   onNewChat,
                                   onDeleteSession,
                                   onAfterAction,
                               }: SidebarContentProps) {
    const handle = (action: () => void) => () => {
        action();
        onAfterAction?.();
    };

    return (
        <div className="flex h-full flex-col bg-sidebar">
            <div className="p-3">
                <Button className="w-full justify-start gap-2" onClick={handle(onNewChat)}>
                    <Plus className="size-4"/>
                    Cuộc trò chuyện mới
                </Button>
            </div>

            <Separator/>

            <div className="flex items-center justify-between px-3 py-2">
                <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    Lịch sử
                </span>
                <Badge variant="muted">{sessions.length}</Badge>
            </div>

            <ScrollArea className="flex-1">
                <ul className="space-y-1 px-2 pb-3">
                    {sessions.length === 0 && (
                        <li className="px-2 py-6 text-center text-xs text-muted-foreground">
                            Chưa có cuộc trò chuyện nào
                        </li>
                    )}
                    {sessions.map((session) => (
                        <SessionRow
                            key={session.id}
                            session={session}
                            active={session.id === currentSessionId}
                            onSelect={handle(() => onSelectSession(session.id))}
                            onDelete={handle(() => onDeleteSession(session.id))}
                        />
                    ))}
                </ul>
            </ScrollArea>
        </div>
    );
}

/** Một dòng session trong sidebar (tách riêng cho dễ đọc; nút xoá chỉ hiện khi hover/focus). */
function SessionRow({
                        session,
                        active,
                        onSelect,
                        onDelete,
                    }: {
    session: ChatSession;
    active: boolean;
    onSelect: () => void;
    onDelete: () => void;
}) {
    return (
        <li className="group relative">
            <button
                type="button"
                onClick={onSelect}
                aria-current={active ? 'true' : undefined}
                aria-label={`${session.title} (${session.messageCount} tin nhắn)`}
                className={`flex w-full items-start gap-2 rounded-lg border px-2.5 py-2 pr-8 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
                    active
                        ? 'border-primary/40 bg-primary/10'
                        : 'border-transparent hover:border-border hover:bg-muted/60'
                }`}
            >
                <MessageSquare className="mt-0.5 size-4 shrink-0 text-muted-foreground"/>
                <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-foreground">{session.title}</span>
                    <span className="block text-xs text-muted-foreground">{session.messageCount} tin nhắn</span>
                </span>
            </button>
            <button
                type="button"
                onClick={onDelete}
                aria-label={`Xoá cuộc trò chuyện ${session.title}`}
                className="absolute top-1/2 right-1.5 -translate-y-1/2 rounded-md p-1 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
                <Trash2 className="size-3.5"/>
            </button>
        </li>
    );
}

/** Cột cố định cho desktop — ẩn dưới `md` (mobile dùng `Sheet` trong `AppHeader`). */
export function AppSidebar(props: SidebarContentProps) {
    return (
        <aside className="hidden w-64 shrink-0 border-r border-border md:flex md:flex-col">
            <SidebarContent {...props}/>
        </aside>
    );
}
