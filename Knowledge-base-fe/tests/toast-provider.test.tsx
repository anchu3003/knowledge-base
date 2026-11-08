import {describe, expect, it} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import {ToastProvider, useToast} from '@/components/toast-provider';

/** Component nhỏ dùng hook để bắn toast — giống cách `message-with-citations` sẽ dùng. */
function Trigger() {
    const {toast} = useToast();
    return (
        <button type="button" onClick={() => toast({title: 'Đã copy', description: 'Câu trả lời đã vào clipboard'})}>
            copy
        </button>
    );
}

describe('ToastProvider (KB-4.8)', () => {
    it('bắn toast ⇒ hiện title + description', async () => {
        const user = userEvent.setup();
        render(
            <ToastProvider>
                <Trigger/>
            </ToastProvider>,
        );

        expect(screen.queryByText('Đã copy')).not.toBeInTheDocument();
        await user.click(screen.getByRole('button', {name: 'copy'}));

        expect(await screen.findByText('Đã copy')).toBeInTheDocument();
        expect(screen.getByText('Câu trả lời đã vào clipboard')).toBeInTheDocument();
    });

    it('useToast ngoài provider ⇒ no-op, không throw (test component lẻ)', async () => {
        const user = userEvent.setup();
        render(<Trigger/>);

        await user.click(screen.getByRole('button', {name: 'copy'}));
        expect(screen.queryByText('Đã copy')).not.toBeInTheDocument();
    });
});
