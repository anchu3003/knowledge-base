import {describe, expect, it, vi} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {SourcesPanel, citationLabel, shortChunkId, snippetView} from '@/components/sources-panel';

const chunk = (overrides: Record<string, unknown>) => ({
    file_path: 'docs/java.md',
    file_name: 'java.md',
    file_type: 'markdown',
    relevance_score: 0.8,
    ...overrides,
});

// 3 chunk CÙNG một file — ca TD-12 (trước KB-4.3 bị dedup còn 1 card)
const sources = [
    chunk({citation_id: 'S1', chunk_id: 'aaaaaaaa1111', heading_path: 'Java > Collections', snippet: 'ArrayList'}),
    chunk({citation_id: 'S2', chunk_id: 'bbbbbbbb2222', heading_path: 'Java > Streams', snippet: 'Stream API'}),
    chunk({citation_id: 'S3', chunk_id: 'cccccccc3333', snippet: 'x'.repeat(500)}),
];

describe('SourcesPanel (KB-4.3)', () => {
    it('3 chunk cùng file ⇒ 3 card, mỗi card một citation_id', () => {
        render(<SourcesPanel sources={sources}/>);

        expect(screen.getByTestId('source-card-S1')).toBeInTheDocument();
        expect(screen.getByTestId('source-card-S2')).toBeInTheDocument();
        expect(screen.getByTestId('source-card-S3')).toBeInTheDocument();
        expect(screen.getByText('Nguồn (3)')).toBeInTheDocument();
    });

    it('hiện heading_path + chunk_id dạng ngắn + footer metadata', () => {
        render(<SourcesPanel sources={sources} metadata={{model: 'gpt-4o-mini', retrieved_documents: 3}}/>);

        expect(screen.getByText('Java > Collections')).toBeInTheDocument();
        expect(screen.getByText('chunk #aaaaaaaa')).toBeInTheDocument();
        expect(screen.getByText('gpt-4o-mini')).toBeInTheDocument();
        expect(screen.getByText('3 tài liệu đã truy hồi')).toBeInTheDocument();
    });

    it('bấm chip [S2] ⇒ card S2 được scroll + highlight, S1 thì không', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView');
        const {rerender} = render(<SourcesPanel sources={sources}/>);

        rerender(<SourcesPanel sources={sources} highlightCitationId="S2" highlightNonce={1}/>);

        expect(scrollSpy).toHaveBeenCalled();
        expect(screen.getByTestId('source-card-S2').className).toContain('ring-2');
        expect(screen.getByTestId('source-card-S1').className).not.toContain('ring-2');
    });

    it('snippet dài có nút Xem thêm → Thu gọn', async () => {
        render(<SourcesPanel sources={sources}/>);

        const toggle = screen.getByRole('button', {name: /Xem thêm/});
        await userEvent.click(toggle);

        expect(screen.getByRole('button', {name: /Thu gọn/})).toBeInTheDocument();
    });

    it('không có nguồn ⇒ render rỗng', () => {
        const {container} = render(<SourcesPanel sources={[]}/>);

        expect(container).toBeEmptyDOMElement();
    });
});

describe('helpers của SourcesPanel', () => {
    it('citationLabel ưu tiên citation_id, fallback theo index', () => {
        expect(citationLabel({citation_id: 'S7'} as never, 0)).toBe('S7');
        expect(citationLabel({} as never, 2)).toBe('S3');
    });

    it('shortChunkId cắt 8 ký tự, thiếu chunk_id ⇒ null', () => {
        expect(shortChunkId('abcdef123456')).toBe('abcdef12');
        expect(shortChunkId(undefined)).toBeNull();
    });

    it('snippetView fallback content_preview (BE cũ) + đánh dấu truncated', () => {
        const legacy = snippetView({content_preview: 'preview'} as never, false);
        expect(legacy).toEqual({text: 'preview', truncated: false});

        const long = snippetView({snippet: 'y'.repeat(500)} as never, false);
        expect(long.truncated).toBe(true);
        expect(long.text.endsWith('…')).toBe(true);
    });
});
