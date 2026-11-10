import {createServer} from 'node:http';
import type {AddressInfo} from 'node:net';

import {expect, test, type Page} from '@playwright/test';

/**
 * Smoke UI bằng Chromium thật (KB-4.9) — thay `tools/ui-verify.*` (CDP qua Chrome Windows).
 *
 * Nguyên tắc: mỗi test **tự dựng state** qua `localStorage` (không gọi LLM ⇒ không tốn quota) rồi kiểm
 * thứ mà unit test không thấy được: layout, tràn ngang, focus trap, theme, persist sau reload.
 * KB-4.11 thêm 2 test dùng **SSE server thật** (node:http stream từng frame) để thấy pha truy hồi → đang viết.
 */

const STORE_KEY = 'kb.chat_sessions';
const THEME_KEY = 'kb.theme';

interface SeedOptions {
    title?: string;
    question?: string;
    answer?: string;
    sources?: Array<Record<string, unknown>>;
}

/** Seed 1 session vào store của app (đúng schema `lib/chat-store.ts`) rồi để app tự đọc lại. */
async function seedSession(page: Page, options: SeedOptions = {}) {
    const {
        title = 'Kiểm tra F5',
        question = 'Câu hỏi kiểm tra F5',
        answer = 'Trả lời **giữ sau reload**',
        sources,
    } = options;

    await page.addInitScript(
        ({key, value}) => window.localStorage.setItem(key, value),
        {
            key: STORE_KEY,
            value: JSON.stringify({
                version: 1,
                currentSessionId: 's-e2e',
                sessions: [
                    {
                        id: 's-e2e',
                        title,
                        createdAt: new Date().toISOString(),
                        messageCount: 2,
                        conversationId: 'conv-e2e',
                        messages: [
                            {id: 'm1', role: 'user', content: question},
                            {
                                id: 'm2',
                                role: 'assistant',
                                content: answer,
                                metadata: {model: 'openai/gpt-oss-120b', retrieved_documents: sources?.length ?? 0},
                                ...(sources ? {sources} : {}),
                            },
                        ],
                    },
                ],
            }),
        },
    );
}

/** Phần tử nào đang làm trang tràn ngang (log ra khi assert fail, thay vì chỉ báo "overflow"). */
async function overflowReport(page: Page) {
    return page.evaluate(() => {
        const viewport = window.innerWidth;
        const offenders: Array<{tag: string; cls: string; width: number; pastRight: number; text: string}> = [];
        document.querySelectorAll('*').forEach((el) => {
            const rect = el.getBoundingClientRect();
            if (rect.right > viewport + 1) {
                offenders.push({
                    tag: el.tagName.toLowerCase(),
                    cls: String(el.className ?? '').slice(0, 80),
                    width: Math.round(rect.width),
                    pastRight: Math.round(rect.right - viewport),
                    text: (el.textContent ?? '').trim().slice(0, 40),
                });
            }
        });
        return {
            viewport,
            documentWidth: document.documentElement.scrollWidth,
            overflow: document.documentElement.scrollWidth - viewport,
            offenders: offenders.slice(0, 8),
        };
    });
}

/** Panel nguồn không được rộng hơn cột chat (composer) — đây mới là triệu chứng user thấy:
 * card nguồn thò ra ngoài bubble. ScrollArea che bằng `overflow:hidden` nên `document.scrollWidth`
 * KHÔNG bắt được ⇒ phải so sánh trực tiếp kích thước. */
async function expectSourcesWithinColumn(page: Page) {
    const sources = page.locator('[aria-label="Nguồn tham khảo"]');
    const composer = page.getByTestId('composer-row');
    const sourcesBox = await sources.boundingBox();
    const composerBox = await composer.boundingBox();
    expect(sourcesBox, 'sources panel').not.toBeNull();
    expect(composerBox, 'composer').not.toBeNull();

    const overflowsContainer = await sources.evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(Math.round(sourcesBox!.width), 'panel nguồn rộng hơn cột chat').toBeLessThanOrEqual(
        Math.round(composerBox!.width) + 2,
    );
    expect(overflowsContainer, 'nội dung nguồn tràn trong panel').toBeLessThanOrEqual(2);
}

test.describe('Shell & layout', () => {
    test('header có brand, đúng MỘT nút "Kho tài liệu", toggle theme', async ({page}) => {
        await page.goto('/');
        await expect(page.locator('header')).toContainText('Knowledge Base');
        await expect(page.getByRole('button', {name: 'Kho tài liệu'})).toHaveCount(1);
        await expect(page.locator('header button[data-theme-mode]')).toBeVisible();
        await page.screenshot({path: 'test-results/shot-01-home.png'});
    });

    test('ngăn kéo: brand ở trên, nút đóng nằm trong khung và không đè nút Tạo mới (KB-5.12)', async ({page}) => {
        await page.route('**/conversations', (route) =>
            route.fulfill({status: 200, contentType: 'application/json',
                body: JSON.stringify({conversations: [], total: 0})}),
        );
        await page.goto('/');
        await page.getByRole('button', {name: 'Mở lịch sử trò chuyện'}).click();

        const drawer = page.getByRole('dialog');
        const closeButton = drawer.getByRole('button', {name: 'Đóng lịch sử'});
        const newChat = drawer.getByRole('button', {name: /Cuộc trò chuyện mới/});
        await expect(drawer.getByText('Knowledge Base')).toBeVisible();
        await expect(closeButton).toBeVisible();

        const [drawerBox, closeBox, newChatBox] = await Promise.all([
            drawer.boundingBox(), closeButton.boundingBox(), newChat.boundingBox(),
        ]);
        // nút đóng nằm trong khung ngăn kéo
        expect(closeBox!.x + closeBox!.width).toBeLessThanOrEqual(drawerBox!.x + drawerBox!.width + 0.5);
        // và ở HÀNG TRÊN nút "Cuộc trò chuyện mới" (bug cũ: nút X mặc định đè lên nút này)
        expect(closeBox!.y + closeBox!.height).toBeLessThanOrEqual(newChatBox!.y + 0.5);

        await closeButton.click();
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await page.screenshot({path: 'test-results/shot-15-drawer-closed.png'});
    });

    test('720px: không cột sidebar, ngăn kéo Lịch sử mở được, không tràn ngang', async ({page}) => {
        await page.setViewportSize({width: 720, height: 900});
        await page.goto('/');
        // KB-5.11: bỏ hẳn cột `aside` — hội thoại nằm trong ngăn kéo
        await expect(page.locator('aside')).toHaveCount(0);
        await expect(page.getByRole('button', {name: 'Mở lịch sử trò chuyện'})).toBeVisible();

        const report = await overflowReport(page);
        expect(report.overflow, JSON.stringify(report, null, 2)).toBeLessThanOrEqual(0);
        await page.screenshot({path: 'test-results/shot-02-720.png'});
    });
});


test.describe('Theme', () => {
    test('sáng → tối: đổi class .dark + color-scheme + lưu localStorage', async ({page}) => {
        await page.goto('/');
        const toggle = page.locator('header button[data-theme-mode]');

        await toggle.click(); // system → light
        await expect(page.locator('html')).not.toHaveClass(/dark/);
        expect(await page.evaluate((key) => window.localStorage.getItem(key), THEME_KEY)).toBe('light');
        await page.screenshot({path: 'test-results/shot-03-light.png'});

        await toggle.click(); // light → dark
        await expect(page.locator('html')).toHaveClass(/dark/);
        expect(await page.evaluate(() => document.documentElement.style.colorScheme)).toBe('dark');
        await page.screenshot({path: 'test-results/shot-04-dark.png'});
    });
});

test.describe('Lịch sử hội thoại (KB-4.9)', () => {
    test('F5 vẫn thấy hội thoại + tiêu đề session (localStorage)', async ({page}) => {
        await seedSession(page);
        await page.goto('/');

        await expect(page.getByText('Câu hỏi kiểm tra F5')).toBeVisible();
        // KB-5.11: danh sách hội thoại nằm trong ngăn kéo ⇒ mở rồi mới thấy tiêu đề
        await page.getByRole('button', {name: 'Mở lịch sử trò chuyện'}).click();
        const drawer = page.getByRole('dialog');
        await expect(drawer.getByText('Kiểm tra F5', {exact: true})).toBeVisible();
        // KB-5.11: nút xoá phải **nằm trong** ngăn kéo. Bug thật đã gặp: Radix `ScrollArea` bọc nội dung trong
        // `display: table` ⇒ tiêu đề dài làm dòng rộng quá drawer và đẩy nút xoá ra ngoài (x=363 > 288).
        // `toBeVisible()` không bắt được lỗi này vì phần tử vẫn "visible" dù ở ngoài khung nhìn.
        const deleteButton = drawer.getByRole('button', {name: /Xoá cuộc trò chuyện/}).first();
        await expect(deleteButton).toBeVisible();
        const [drawerBox, deleteBox] = await Promise.all([drawer.boundingBox(), deleteButton.boundingBox()]);
        expect(deleteBox!.x + deleteBox!.width).toBeLessThanOrEqual(drawerBox!.x + drawerBox!.width + 0.5);
        await page.keyboard.press('Escape');
        await expect(page.locator('.md-body strong')).toHaveText('giữ sau reload'); // markdown render thật
    });
});

test.describe('Kho tài liệu (Sheet)', () => {
    test('mở: role=dialog, focus nằm trong sheet, ESC đóng', async ({page}) => {
        await page.goto('/');
        await page.getByRole('button', {name: 'Kho tài liệu'}).click();

        const sheet = page.locator('[data-slot="sheet-content"]');
        await expect(sheet).toBeVisible();
        await expect(sheet).toHaveAttribute('role', 'dialog');
        await expect(sheet).toHaveAttribute('aria-labelledby', /.+/);
        expect(await sheet.evaluate((el) => el.contains(document.activeElement))).toBe(true);
        await page.screenshot({path: 'test-results/shot-05-sheet.png'});

        await page.keyboard.press('Escape');
        await expect(sheet).toBeHidden();
    });
});

test.describe('Panel Nguồn', () => {
    test('Nguồn dài (path + snippet) KHÔNG làm tràn ngang', async ({page}) => {
        const longSnippet =
            'Design patterns are essential in Java backend development to create scalable, maintainable, and efficient applications. ' +
            'RabbitMQJava Client (com.rabbitmq.client.Channel) - Commonly Used APIs > Utility Methods > boolean isOpen()';

        await seedSession(page, {
            title: 'Hi',
            question: 'Hi',
            answer: 'Hi! How can I assist you today?',
            sources: [
                {
                    citation_id: 'S1',
                    chunk_id: '29442be8aaaaaaaa',
                    file_name: 'Design patterns & Architecture.md',
                    file_path: 'Interview/Backend&Devops/Design patterns & Architecture/Design patterns & Architecture.md',
                    file_type: 'md',
                    relevance_score: 0.083,
                    heading_path: 'Design patterns > Creational',
                    snippet: longSnippet,
                },
                {
                    citation_id: 'S2',
                    chunk_id: '48d9c2edcccccccc',
                    file_name: 'Rabbitmq.md',
                    // path + token không có dấu cách: đây là thứ làm max-content phình ra và gây tràn ngang
                    file_path:
                        'Interview/Backend&Devops/Rabbitmq/com.rabbitmq.client.Channel/boolean.isOpen.CheckChannelIsActive.md',
                    file_type: 'md',
                    relevance_score: 0.004,
                    heading_path: 'Utility Methods > com.rabbitmq.client.Channel > boolean isOpen()',
                    snippet: 'booleanisOpenRabbitMQJavaClientcom.rabbitmq.client.ChannelCheckifChannelisActive.handles_supercalifragilisticexpialidocious',
                },
            ],
        });
        await page.goto('/');
        await expect(page.locator('[aria-label="Nguồn tham khảo"]')).toBeVisible();

        const report = await overflowReport(page);
        expect(report.overflow, JSON.stringify(report, null, 2)).toBeLessThanOrEqual(0);
        await expectSourcesWithinColumn(page);

        await page.screenshot({path: 'test-results/shot-06-sources.png', fullPage: true});
    });
});

    test('1900px (cửa sổ rộng) vẫn không tràn ngang', async ({page}) => {
        await page.setViewportSize({width: 1900, height: 1000});
        await seedSession(page, {
            title: 'Hi',
            question: 'Hi',
            answer: 'Hi! How can I assist you today?',
            sources: [
                {
                    citation_id: 'S1',
                    chunk_id: '29442be8aaaaaaaa',
                    file_name: 'Design patterns & Architecture.md',
                    file_path:
                        'Interview/BackendDevops/DesignpatternsArchitecture/DesignpatternsArchitectureWithAVeryLongFileNameWithoutSpaces.md',
                    file_type: 'md',
                    relevance_score: 0.083,
                    heading_path: 'Design patterns > Creational > FactoryMethodAbstractFactoryBuilderPrototypeSingleton',
                    snippet: 'DesignPatternsAreEssentialInJavaBackendDevelopmentToCreateScalableMaintainableAndEfficientApplications',
                },
            ],
        });
        await page.goto('/');
        await expect(page.locator('[aria-label="Nguồn tham khảo"]')).toBeVisible();

        const report = await overflowReport(page);
        expect(report.overflow, JSON.stringify(report, null, 2)).toBeLessThanOrEqual(0);
        await expectSourcesWithinColumn(page);
        await page.screenshot({path: 'test-results/shot-07-1900-sources.png'});
    });
test.describe('Canh mép cột chat', () => {
    test('composer + panel Nguồn thẳng mép bubble (trái = AI, phải = "Bạn"), composer thấp', async ({page}) => {
        await seedSession(page, {
            title: 'Canh mép',
            question: 'Câu hỏi canh mép',
            answer: 'Trả lời để đo mép bubble của AI',
            sources: [
                {
                    citation_id: 'S1',
                    chunk_id: 'aaaaaaaaaaaaaaa1',
                    file_name: 'Design patterns & Architecture.md',
                    file_path: 'Interview/Backend&Devops/Design patterns & Architecture.md',
                    file_type: 'md',
                    relevance_score: 0.083,
                    heading_path: 'Design patterns > Creational',
                    snippet: 'Design patterns are essential in Java backend development.',
                },
            ],
        });
        await page.goto('/');

        const composer = page.getByTestId('composer-row');
        const aiBubble = page.getByTestId('bubble-assistant');
        const userBubble = page.getByTestId('bubble-user');
        const sources = page.locator('[aria-label="Nguồn tham khảo"]');

        await expect(composer).toBeVisible();
        await expect(aiBubble).toBeVisible();
        await expect(userBubble).toBeVisible();
        await expect(sources).toBeVisible();

        const [composerBox, aiBox, userBox, sourcesBox] = await Promise.all([
            composer.boundingBox(),
            aiBubble.boundingBox(),
            userBubble.boundingBox(),
            sources.boundingBox(),
        ]);

        // mép trái composer = mép trái bubble AI
        expect(Math.abs(composerBox!.x - aiBox!.x), 'mép trái composer vs bubble AI').toBeLessThanOrEqual(1.5);
        // mép phải composer = mép phải bubble "Bạn"
        expect(
            Math.abs(composerBox!.x + composerBox!.width - (userBox!.x + userBox!.width)),
            'mép phải composer vs bubble Bạn',
        ).toBeLessThanOrEqual(1.5);
        // mép phải panel Nguồn = mép phải bubble "Bạn"
        expect(
            Math.abs(sourcesBox!.x + sourcesBox!.width - (userBox!.x + userBox!.width)),
            'mép phải panel Nguồn vs bubble Bạn',
        ).toBeLessThanOrEqual(1.5);

        // composer gọn: ô nhập 1 dòng, không cao như textarea 2 dòng + nút lg
        expect(composerBox!.height, 'chiều cao ô nhập').toBeLessThanOrEqual(42);
        const sendBox = await page.getByRole('button', {name: 'Gửi câu hỏi'}).boundingBox();
        expect(Math.abs(sendBox!.height - composerBox!.height), 'nút gửi cùng chiều cao ô nhập').toBeLessThanOrEqual(2);

        await page.screenshot({path: 'test-results/shot-08-alignment.png'});
    });
});

/**
 * SSE server thật (node:http) để test pha `retrieving → writing`.
 *
 * `route.fulfill()` trả **toàn bộ** body một lần ⇒ UI nhảy thẳng từ "đang truy hồi" sang câu trả lời,
 * không quan sát được pha "đang viết". Server này gửi từng frame cách nhau `delayMs` như BE thật.
 */
async function startSseServer(frames: Array<{delayMs: number; payload: Record<string, unknown>}>) {
    const server = createServer((req, res) => {
        if (req.method === 'OPTIONS') {
            res.writeHead(204, {
                'access-control-allow-origin': '*',
                'access-control-allow-headers': '*',
                'access-control-allow-methods': 'POST, OPTIONS',
            });
            res.end();
            return;
        }

        res.writeHead(200, {
            'content-type': 'text/event-stream',
            'cache-control': 'no-cache',
            'access-control-allow-origin': '*',
        });

        let index = 0;
        const writeNext = () => {
            if (index >= frames.length) {
                res.end();
                return;
            }
            const frame = frames[index];
            index += 1;
            setTimeout(() => {
                res.write(`data: ${JSON.stringify(frame.payload)}\n\n`);
                writeNext();
            }, frame.delayMs);
        };
        writeNext();
    });

    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    const {port} = server.address() as AddressInfo;
    return {
        url: `http://127.0.0.1:${port}/chat/stream`,
        close: () => new Promise<void>((resolve) => server.close(() => resolve())),
    };
}

test.describe('Stream: plain text khi đang viết, markdown khi xong (KB-5.6)', () => {
    test('chip [S1] chỉ xuất hiện sau `end` (không parse markdown mỗi token)', async ({page}) => {
        const sse = await startSseServer([
            {delayMs: 0, payload: {type: 'start', conversation_id: 'conv-kb56', metadata: {model: 'openai/gpt-oss-120b'}}},
            // KB-5.11: nới khoảng cách token — bản production build nhanh nên cửa sổ "đang stream" quá ngắn,
            // test từng flaky (assert `chip chưa có` chạy sau khi `end` đã tới).
            {delayMs: 800, payload: {type: 'token', token: '**Đậm** và '}},
            {delayMs: 2500, payload: {type: 'token', token: 'nguồn [S1]'}},
            {
                delayMs: 300,
                payload: {
                    type: 'end',
                    answer: '**Đậm** và nguồn [S1]',
                    sources: [{
                        citation_id: 'S1',
                        chunk_id: 'bbbbbbbbbbbbbbb1',
                        file_name: 'Kafka.md',
                        file_path: 'Interview/Messaging/Kafka.md',
                        file_type: 'md',
                        relevance_score: 0.91,
                        snippet: 'Kafka là message broker.',
                    }],
                    metadata: {model: 'openai/gpt-oss-120b'},
                },
            },
        ]);

        try {
            // KB-5.11: BE thật có thể đã lưu nhiều hội thoại (KB-5.2) ⇒ app nạp lại và **đã có sẵn** chip [S1],
            // làm assert `chip chưa xuất hiện` sai. Cô lập test: server trả danh sách rỗng.
            await page.route('**/conversations', (route) =>
                route.fulfill({status: 200, contentType: 'application/json',
                    body: JSON.stringify({conversations: [], total: 0})}),
            );
            await page.route('**/chat/stream', (route) =>
                route.continue({url: sse.url, headers: {...route.request().headers()}}),
            );

            await page.goto('/');
            await page.getByRole('textbox', {name: 'Câu hỏi'}).fill('Câu hỏi kiểm tra stream');
            await page.getByRole('button', {name: 'Gửi câu hỏi'}).click();

            // Đang stream: nội dung là plain text, `**Đậm**` hiện nguyên dấu sao, chưa có chip
            const plain = page.getByTestId('streaming-plaintext');
            await expect(plain).toBeVisible({timeout: 5000});
            await expect(plain).toContainText('**Đậm**');
            await expect(page.getByRole('button', {name: 'Xem nguồn S1'})).toHaveCount(0);

            // `end` tới: markdown render (Đậm thành <strong>) + chip [S1] bấm được
            await expect(page.getByRole('button', {name: 'Xem nguồn S1'})).toBeVisible({timeout: 5000});
            await expect(page.locator('strong', {hasText: 'Đậm'})).toBeVisible();
            await expect(page.getByTestId('streaming-plaintext')).toHaveCount(0);
            await page.screenshot({path: 'test-results/shot-14-markdown-after-end.png'});
        } finally {
            await sse.close();
        }
    });
});

test.describe('Pha truy hồi & answer rỗng (KB-4.11)', () => {
    test('hiện "Đang truy hồi tài liệu (ns)" rồi "Đang viết câu trả lời"', async ({page}) => {
        // Mô phỏng BE thật: `start` tới sau 2.5s (redanch CPU ~12.9s — TD-15), token cách 1.2s
        const sse = await startSseServer([
            {delayMs: 2500, payload: {type: 'start', conversation_id: 'conv-e2e', metadata: {model: 'openai/gpt-oss-120b'}}},
            {delayMs: 1200, payload: {type: 'token', token: 'Xin chào'}},
            {delayMs: 200, payload: {type: 'end', answer: 'Xin chào', sources: [], metadata: {model: 'openai/gpt-oss-120b'}}},
        ]);

        try {
            await page.route('**/chat/stream', (route) =>
                route.continue({url: sse.url, headers: {...route.request().headers()}}),
            );

            await page.goto('/');
            await page.getByRole('textbox', {name: 'Câu hỏi'}).fill('Câu hỏi kiểm tra pha');
            await page.getByRole('button', {name: 'Gửi câu hỏi'}).click();

            const status = page.getByTestId('stream-phase');
            // Pha 1: chưa có `start` ⇒ nhãn truy hồi + số giây
            await expect(status).toContainText('Đang truy hồi tài liệu', {timeout: 2000});
            await expect(status).toContainText(/\(\d+s\)/);
            await page.screenshot({path: 'test-results/shot-09-retrieving.png'});

            // Pha 2: nhận `start`, chưa có token ⇒ "đang viết"
            await expect(status).toContainText('Đang viết câu trả lời', {timeout: 5000});
            await page.screenshot({path: 'test-results/shot-10-writing.png'});

            // Token tới ⇒ khối trạng thái biến mất, câu trả lời hiện
            await expect(page.getByText('Xin chào')).toBeVisible({timeout: 5000});
            await expect(status).toBeHidden();
        } finally {
            await sse.close();
        }
    });

    test('answer rỗng: hiện giải thích + nút Thử lại, không có bubble trống', async ({page}) => {
        const sse = await startSseServer([
            {delayMs: 0, payload: {type: 'start', conversation_id: 'conv-empty', metadata: {model: 'openai/gpt-oss-120b'}}},
            {delayMs: 100, payload: {type: 'end', answer: '   ', sources: [], metadata: {model: 'openai/gpt-oss-120b'}}},
        ]);

        try {
            await page.route('**/chat/stream', (route) =>
                route.continue({url: sse.url, headers: {...route.request().headers()}}),
            );

            await page.goto('/');
            await page.getByRole('textbox', {name: 'Câu hỏi'}).fill('Câu hỏi trả về rỗng');
            await page.getByRole('button', {name: 'Gửi câu hỏi'}).click();

            const notice = page.getByTestId('empty-answer');
            await expect(notice).toBeVisible({timeout: 8000});
            await expect(notice).toContainText('Model không trả về nội dung');
            await expect(page.getByRole('button', {name: 'Thử lại'})).toBeVisible();
            await page.screenshot({path: 'test-results/shot-11-empty-answer.png'});
        } finally {
            await sse.close();
        }
    });
});
test.describe('Đồng bộ tài liệu (KB-5.1)', () => {
    test('bấm "Đồng bộ file mới" ⇒ hiện kết quả, không còn nút Refresh toàn bộ', async ({page}) => {
        // Stub các endpoint đọc trạng thái để panel mở được (không phụ thuộc BE thật)
        await page.route('**/documents/status', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({collection_name: 'documents', document_count: 603, status: 'healthy'}),
            }),
        );
        await page.route('**/documents/folder-info', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    folder_path: '/app/Interview',
                    exists: true,
                    total_files: 67,
                    supported_files_count: 56,
                }),
            }),
        );
        await page.route('**/ready', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({status: 'ok', checks: {collection: {ok: true, detail: 'ok'}}}),
            }),
        );
        await page.route('**/documents/sync', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    success: true,
                    message: '+1 mới, ~0 cập nhật, -0 xoá',
                    added: ['ghi-chu-moi.md'],
                    updated: [],
                    removed: [],
                    skipped: [{path: 'Interview/Messaging/Kafka.md', reason: 'empty_file: 0 bytes'}],
                    unchanged: 46,
                    total_chunks: 2,
                    removed_chunks: 0,
                    elapsed_ms: 1233,
                    details: [],
                }),
            }),
        );

        await page.goto('/');
        await page.getByRole('button', {name: 'Kho tài liệu'}).click();
        const sheet = page.locator('[data-slot="sheet-content"]');
        await expect(sheet).toBeVisible();

        // Q3 = B: nút Refresh toàn bộ đã bị bỏ khỏi UI
        await expect(sheet.getByRole('button', {name: /Refresh/i})).toHaveCount(0);

        await sheet.getByRole('button', {name: /Đồng bộ file mới/}).click();

        const result = page.getByTestId('sync-result');
        await expect(result).toBeVisible({timeout: 10_000});
        await expect(result).toContainText('1 mới');
        await expect(result).toContainText('2 chunk mới');
        await expect(result).toContainText('1.2s');
        await expect(result).toContainText('Kafka.md');
        await page.screenshot({path: 'test-results/shot-12-sync-result.png'});
    });
});
test.describe('Lịch sử hội thoại bền (KB-5.2)', () => {
    test('máy khác (localStorage rỗng) vẫn thấy hội thoại từ server + nạp messages', async ({page}) => {
        // Server là nguồn sự thật: list + detail được stub, localStorage cố tình để trống.
        await page.route('**/conversations', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    conversations: [
                        {
                            id: 'conv-server-1',
                            title: 'Kafka là gì?',
                            created_at: '2026-01-02T10:00:00',
                            updated_at: '2026-01-02T10:05:00',
                            message_count: 2,
                        },
                    ],
                    total: 1,
                }),
            }),
        );
        await page.route('**/conversations/conv-server-1', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    id: 'conv-server-1',
                    title: 'Kafka là gì?',
                    created_at: '2026-01-02T10:00:00',
                    updated_at: '2026-01-02T10:05:00',
                    messages: [
                        {role: 'user', content: 'Kafka là gì?', timestamp: '2026-01-02T10:00:00'},
                        {role: 'assistant', content: 'Là message broker phân tán.', timestamp: '2026-01-02T10:00:05'},
                    ],
                }),
            }),
        );

        await page.goto('/');

        // Sidebar hiện session của server (không có trong localStorage)
        await expect(page.getByText('Kafka là gì?').first()).toBeVisible({timeout: 10_000});
        // Messages nạp lazy từ GET /conversations/{id}
        await expect(page.getByText('Là message broker phân tán.')).toBeVisible({timeout: 10_000});
        await page.screenshot({path: 'test-results/shot-13-server-history.png'});
    });

    test('BE tắt (mọi endpoint lỗi) ⇒ vẫn dùng được lịch sử localStorage, không trắng màn hình', async ({page}) => {
        await page.route('**/conversations**', (route) => route.abort('failed'));

        // Có sẵn 1 session trong localStorage (như user đã chat trước đó)
        await page.addInitScript(() => {
            window.localStorage.setItem('kb.chat_sessions', JSON.stringify({
                version: 1,
                currentSessionId: 'session_local',
                sessions: [{
                    id: 'session_local',
                    title: 'Hội thoại offline',
                    createdAt: '2026-01-01T00:00:00.000Z',
                    messageCount: 2,
                    conversationId: 'conv-cu',
                    messages: [
                        {id: 'u1', role: 'user', content: 'Câu hỏi cũ của tôi'},
                        {id: 'a1', role: 'assistant', content: 'Câu trả lời cũ'},
                    ],
                }],
            }));
        });

        await page.goto('/');

        // messages của session đang mở vẫn hiện (không cần mở ngăn kéo)
        await expect(page.getByText('Câu trả lời cũ')).toBeVisible();
        await expect(page.getByRole('button', {name: 'Kho tài liệu'})).toBeVisible(); // app vẫn render
        // tiêu đề session nằm trong ngăn kéo
        await page.getByRole('button', {name: 'Mở lịch sử trò chuyện'}).click();
        await expect(page.getByRole('dialog').getByText('Hội thoại offline')).toBeVisible();
    });
});
