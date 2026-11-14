/**
 * Đo chi phí render khi stream (KB-5.6 — trả TD-21).
 *
 * Ý tưởng: mock `MarkdownMessage` để **đếm số lần parse markdown**. Trước KB-5.6, mỗi token làm
 * `markdown-message` render lại toàn bộ câu trả lời ⇒ 300 token = 300 lần render (O(n²) trên tổng
 * ký tự). Sau KB-5.6: lúc stream hiển thị plain text (0 lần parse), chỉ parse **1 lần** khi `end`.
 */

import {render} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';

import {ChatMessages} from '@/components/chat-messages';
import type {ChatMessage} from '@/lib/types';

const markdown = vi.hoisted(() => ({renders: 0, contents: [] as string[]}));

vi.mock('@/components/markdown-message', () => ({
    MarkdownMessage: ({content}: {content: string}) => {
        markdown.renders += 1;
        markdown.contents.push(content);
        return <div data-testid="markdown">{content}</div>;
    },
}));

const TOKEN = 'token ';
const TOKENS = 300;
const FULL = TOKEN.repeat(TOKENS);

function assistant(content: string, overrides: Partial<ChatMessage> = {}): ChatMessage {
    return {id: 'a-stream', role: 'assistant', content, ...overrides};
}

function noop() {
    // callback ổn định (không tạo closure mới mỗi render)
}

function renderList(messages: ChatMessage[]) {
    return render(
        <ChatMessages
            messages={messages}
            isLoading={messages.some((message) => message.isStreaming)}
            citationFocus={null}
            onCitationClick={noop}
        />,
    );
}

describe('chi phí render khi stream (TD-21)', () => {
    it('300 token stream ⇒ số lần parse markdown (trước: 300, sau: 0) + 1 khi kết thúc', () => {
        markdown.renders = 0;
        markdown.contents = [];

        const {rerender} = renderList([assistant('', {isStreaming: true})]);
        markdown.renders = 0;
        markdown.contents = [];

        for (let index = 1; index <= TOKENS; index += 1) {
            rerender(
                <ChatMessages
                    messages={[assistant(FULL.slice(0, index * TOKEN.length), {isStreaming: true})]}
                    isLoading
                    citationFocus={null}
                    onCitationClick={noop}
                />,
            );
        }
        const duringStream = markdown.renders;

        // `end` tới ⇒ markdown đầy đủ render đúng 1 lần
        rerender(
            <ChatMessages
                messages={[assistant(FULL)]}
                isLoading={false}
                citationFocus={null}
                onCitationClick={noop}
            />,
        );

        // Số liệu thật in ra để dán vào ticket
        console.log(`[KB-5.6] markdown renders khi stream ${TOKENS} token: ${duringStream}, tổng sau end: ${markdown.renders}`);

        expect(duringStream).toBe(0); // trước KB-5.6: 300
        expect(markdown.renders).toBe(1);
        expect(markdown.contents.at(-1)).toBe(FULL);
    });

    it('message đã xong KHÔNG render lại khi message khác đang stream', () => {
        markdown.renders = 0;
        markdown.contents = [];

        const done = assistant('câu trả lời cũ đã hoàn chỉnh', {id: 'a-done'});
        const {rerender} = renderList([done, assistant('', {isStreaming: true})]);
        markdown.renders = 0;
        markdown.contents = [];

        for (let index = 1; index <= 20; index += 1) {
            rerender(
                <ChatMessages
                    messages={[done, assistant(FULL.slice(0, index * TOKEN.length), {isStreaming: true})]}
                    isLoading
                    citationFocus={null}
                    onCitationClick={noop}
                />,
            );
        }

        console.log(`[KB-5.6] markdown renders của message cũ khi message khác stream: ${markdown.renders}`);

        expect(markdown.renders).toBe(0); // trước KB-5.6: 20
    });
});
