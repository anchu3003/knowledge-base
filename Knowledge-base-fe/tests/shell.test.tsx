import {describe, expect, it, vi} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import {AppHeader} from '@/components/app-header';
import {SidebarContent, type ChatSession} from '@/components/app-sidebar';
import {TooltipProvider} from '@/components/ui/tooltip';

const sessions: ChatSession[] = [
    {id: 's1', title: 'Ôn phỏng vấn RAG', createdAt: new Date(0), messageCount: 4},
    {id: 's2', title: 'Ghi chú Docker', createdAt: new Date(0), messageCount: 1},
];

function renderSidebar(overrides: Partial<React.ComponentProps<typeof SidebarContent>> = {}) {
    return render(
        <SidebarContent
            sessions={sessions}
            currentSessionId="s1"
            onSelectSession={vi.fn()}
            onNewChat={vi.fn()}
            onDeleteSession={vi.fn()}
            {...overrides}
        />,
    );
}

describe('AppHeader (KB-4.8)', () => {
    it('hiện brand + nút Kho tài liệu + theme toggle, KHÔNG còn user/logout giả', () => {
        render(
            <TooltipProvider>
                <AppHeader onOpenDocuments={vi.fn()}/>
            </TooltipProvider>,
        );

        expect(screen.getByText('Knowledge Base')).toBeInTheDocument();
        expect(screen.getByRole('button', {name: 'Mở kho tài liệu'})).toBeInTheDocument();
        expect(screen.getByRole('button', {name: /Giao diện:/})).toBeInTheDocument();
        // Bản onboarding cũ có "An Chu" + "Logout" (không có auth ở BE)
        expect(screen.queryByText('An Chu')).not.toBeInTheDocument();
        expect(screen.queryByRole('button', {name: /Logout/i})).not.toBeInTheDocument();
    });

    it('bấm Kho tài liệu gọi callback', async () => {
        const user = userEvent.setup();
        const onOpenDocuments = vi.fn();
        render(
            <TooltipProvider>
                <AppHeader onOpenDocuments={onOpenDocuments}/>
            </TooltipProvider>,
        );

        await user.click(screen.getByRole('button', {name: 'Mở kho tài liệu'}));
        expect(onOpenDocuments).toHaveBeenCalledOnce();
    });

    it('có nút mở menu mobile (chỉ hiện ở < md) khi truyền renderMobileSidebar', () => {
        render(
            <TooltipProvider>
                <AppHeader onOpenDocuments={vi.fn()} renderMobileSidebar={() => <div>sidebar</div>}/>
            </TooltipProvider>,
        );

        expect(screen.getByRole('button', {name: 'Mở menu'})).toBeInTheDocument();
    });
});

describe('SidebarContent (KB-4.8)', () => {
    it('liệt kê session + đánh dấu session đang mở', () => {
        renderSidebar();

        expect(screen.getByText('Ôn phỏng vấn RAG')).toBeInTheDocument();
        expect(screen.getByText('Ghi chú Docker')).toBeInTheDocument();
        expect(screen.getByText('4 tin nhắn')).toBeInTheDocument();
        expect(screen.getByText('Lịch sử')).toBeInTheDocument();
        expect(screen.getByRole('button', {name: 'Ôn phỏng vấn RAG (4 tin nhắn)'})).toHaveAttribute('aria-current', 'true');
    });

    it('chọn session + xoá session gọi đúng callback', async () => {
        const user = userEvent.setup();
        const onSelectSession = vi.fn();
        const onDeleteSession = vi.fn();
        renderSidebar({onSelectSession, onDeleteSession});

        await user.click(screen.getByRole('button', {name: 'Ghi chú Docker (1 tin nhắn)'}));
        expect(onSelectSession).toHaveBeenCalledWith('s2');

        await user.click(screen.getByRole('button', {name: 'Xoá cuộc trò chuyện Ôn phỏng vấn RAG'}));
        expect(onDeleteSession).toHaveBeenCalledWith('s1');
    });

    it('KHÔNG còn nút Kho tài liệu trong sidebar (KB-4.9: chỉ giữ ở header)', () => {
        renderSidebar();
        expect(screen.queryByRole('button', {name: 'Mở kho tài liệu'})).not.toBeInTheDocument();
        expect(screen.queryByText('Kho tài liệu')).not.toBeInTheDocument();
    });

    it('rỗng thì hiện empty state + nút chat mới', async () => {
        const user = userEvent.setup();
        const onNewChat = vi.fn();
        renderSidebar({sessions: [], onNewChat});

        expect(screen.getByText('Chưa có cuộc trò chuyện nào')).toBeInTheDocument();
        await user.click(screen.getByRole('button', {name: /Cuộc trò chuyện mới/}));
        expect(onNewChat).toHaveBeenCalledOnce();
    });

    it('onAfterAction chạy sau mỗi hành động (đóng Sheet trên mobile)', async () => {
        const user = userEvent.setup();
        const onAfterAction = vi.fn();
        renderSidebar({onAfterAction});

        await user.click(screen.getByRole('button', {name: 'Ghi chú Docker (1 tin nhắn)'}));
        expect(onAfterAction).toHaveBeenCalledOnce();
    });
});
