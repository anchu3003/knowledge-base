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

    it('có nút "Lịch sử" (mở ngăn kéo) khi truyền renderSidebar — hiện ở mọi kích thước (KB-5.11)', async () => {
        const user = userEvent.setup();
        render(
            <TooltipProvider>
                <AppHeader onOpenDocuments={vi.fn()} renderSidebar={() => <div>sidebar</div>} sessionCount={3}/>
            </TooltipProvider>,
        );

        const trigger = screen.getByRole('button', {name: 'Mở lịch sử trò chuyện'});
        expect(trigger).toBeInTheDocument();
        expect(trigger).not.toHaveClass('md:hidden'); // không còn chỉ-hiện-trên-mobile
        expect(screen.getByText('3')).toBeInTheDocument(); // Badge số phiên

        await user.click(trigger);
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText('sidebar')).toBeInTheDocument();
    });

    it('không còn hamburger "Mở menu" cũ (KB-5.11)', () => {
        render(
            <TooltipProvider>
                <AppHeader onOpenDocuments={vi.fn()} renderSidebar={() => <div>sidebar</div>}/>
            </TooltipProvider>,
        );

        expect(screen.queryByRole('button', {name: 'Mở menu'})).not.toBeInTheDocument();
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

    it('nút xoá LUÔN hiển thị, không cần hover (KB-5.11 — bug "mất nút xoá")', () => {
        renderSidebar();

        for (const title of ['Ôn phỏng vấn RAG', 'Ghi chú Docker']) {
            const button = screen.getByRole('button', {name: `Xoá cuộc trò chuyện ${title}`});
            expect(button).toBeVisible();
            // bug cũ: `opacity-0 group-hover:opacity-100` ⇒ vô hình cho tới khi rê chuột
            expect(button.className).not.toMatch(/opacity-0/);
        }
    });

    it('không còn đường kẻ trang trí trong danh sách (KB-5.11)', () => {
        const {container} = renderSidebar();

        // không có `Separator` (role=separator) và không dùng class border trên dòng session
        expect(container.querySelector('[role="separator"]')).toBeNull();
        expect(container.innerHTML).not.toMatch(/\bborder-border\b/);
    });

    it('header ngăn kéo: brand ở trên, nút đóng chỉ render khi có onClose (KB-5.12)', async () => {
        const user = userEvent.setup();
        const onClose = vi.fn();
        const {unmount} = renderSidebar({onClose});

        expect(screen.getByText('Knowledge Base')).toBeInTheDocument();
        const close = screen.getByRole('button', {name: 'Đóng lịch sử'});
        await user.click(close);
        expect(onClose).toHaveBeenCalledOnce();

        // thứ tự DOM: brand đứng trước "Lịch sử"
        const brand = screen.getByText('Knowledge Base');
        const history = screen.getByText('Lịch sử');
        expect(brand.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

        // không truyền onClose ⇒ không có nút đóng
        unmount();
        renderSidebar();
        expect(screen.queryByRole('button', {name: 'Đóng lịch sử'})).not.toBeInTheDocument();
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
