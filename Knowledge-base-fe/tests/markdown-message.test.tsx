import {describe, expect, it, vi} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {MarkdownMessage, linkifyCitations} from '@/components/markdown-message';

describe('MarkdownMessage (KB-4.2)', () => {
    it('code block có label ngôn ngữ + nút Copy', () => {
        const {container} = render(<MarkdownMessage content={'```python\nprint(1)\n```'}/>);

        expect(screen.getByText('python')).toBeInTheDocument();
        expect(screen.getByRole('button', {name: 'Copy code'})).toBeInTheDocument();
        expect(container.querySelector('code.hljs')).not.toBeNull();
    });

    it('render table GFM (không phải text thuần)', () => {
        const {container} = render(
            <MarkdownMessage content={'| a | b |\n| --- | --- |\n| 1 | 2 |'}/>
        );

        expect(container.querySelector('table')).not.toBeNull();
        expect(screen.getByText('a')).toBeInTheDocument();
    });

    it('`[S1]` thành chip bấm được và gọi onCitationClick với citationId', async () => {
        const onCitationClick = vi.fn();
        render(<MarkdownMessage content={'Xem [S2] để rõ.'} onCitationClick={onCitationClick}/>);

        const chip = screen.getByRole('button', {name: 'Xem nguồn S2'});
        await userEvent.click(chip);

        expect(onCitationClick).toHaveBeenCalledWith('S2');
    });

    it('`[S9]` bên trong code fence KHÔNG thành chip', () => {
        render(<MarkdownMessage content={'```\nvalue = arr[S9]\n```'}/>);

        expect(screen.queryByRole('button', {name: 'Xem nguồn S9'})).toBeNull();
    });

    it('HTML thô trong câu trả lời hiện dạng text (XSS-safe, không dangerouslySetInnerHTML)', () => {
        const {container} = render(
            <MarkdownMessage content={'<img src=x onerror="alert(1)"> an toàn'}/>
        );

        expect(container.querySelector('img')).toBeNull();
        expect(screen.getByText(/an toàn/)).toBeInTheDocument();
    });
});

describe('linkifyCitations (KB-4.2)', () => {
    it('đổi [S1] thành anchor nội bộ, bỏ qua inline code', () => {
        const markdown = linkifyCitations('a [S1] b `[S2]` c');

        expect(markdown).toContain('[S1](#citation-S1)');
        expect(markdown).toContain('`[S2]`');
    });
});
