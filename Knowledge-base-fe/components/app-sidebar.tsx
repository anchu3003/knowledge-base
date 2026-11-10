'use client';

import {MessageSquare, Plus, Trash2} from 'lucide-react';

import {Badge} from '@/components/ui/badge';
import {Button} from '@/components/ui/button';

/**
 * Danh sách hội thoại — **chỉ** render trong ngăn kéo (`Sheet`) từ KB-5.11.
 *
 * Trước KB-5.11: vừa là cột cố định 256px ở desktop (`AppSidebar`), vừa là nội dung drawer mobile ⇒ chat bị
 * thu hẹp + nhiều đường kẻ chia cắt. Nay bỏ cột, bỏ `Separator`/border dòng: phân cấp bằng **khoảng cách + nền**
 * (active `bg-primary/10`, hover `bg-muted`).
 *
 * Nút xoá: trước đây `opacity-0 group-hover:opacity-100` ⇒ **vô hình** với người dùng (bị báo là "mất nút xoá").
 * Nay luôn hiển thị, chỉ đổi màu khi hover.
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
    /** Đóng ngăn kéo sau khi chọn (Sheet luôn truyền) */
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
            <div className="p-3 pb-2">
                <Button className="w-full justify-start gap-2" onClick={handle(onNewChat)}>
                    <Plus className="size-4"/>
                    Cuộc trò chuyện mới
                </Button>
            </div>

            <div className="flex items-center justify-between px-4 pb-1 pt-2">
                <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    Lịch sử
                </span>
                <Badge variant="muted">{sessions.length}</Badge>
            </div>

            {/* KB-5.11: dùng scroll thường thay `ScrollArea` (Radix) — viewport của Radix bọc nội dung trong
                `display: table`, nên tiêu đề dài làm dòng rộng quá ngăn kéo và **đẩy nút xoá ra ngoài**
                (đo được: nút ở x=363 trong khi drawer rộng 288). */}
            <div className="min-h-0 flex-1 overflow-y-auto">
                <ul className="w-full space-y-0.5 px-2 pb-3">
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
            </div>
        </div>
    );
}

/** Một dòng session trong ngăn kéo. Không border; nút xoá **luôn nhìn thấy** (KB-5.11). */
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
                className={`flex w-full items-start gap-2 rounded-lg px-2.5 py-2 pr-9 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
                    active ? 'bg-primary/10' : 'hover:bg-muted'
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
                title="Xoá cuộc trò chuyện"
                className="absolute top-1/2 right-1.5 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
                <Trash2 className="size-3.5"/>
            </button>
        </li>
    );
}
