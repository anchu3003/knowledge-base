import {expect, test, type Page} from '@playwright/test';

/**
 * Smoke UI bằng Chromium thật (KB-4.9) — thay `tools/ui-verify.*` (CDP qua Chrome Windows).
 *
 * Nguyên tắc: mỗi test **tự dựng state** qua `localStorage` (không gọi LLM ⇒ không tốn quota) rồi kiểm
 * thứ mà unit test không thấy được: layout, tràn ngang, focus trap, theme, persist sau reload.
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
    const composer = page.locator('textarea[aria-label="Câu hỏi"]');
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

    test('720px: sidebar ẩn, hamburger hiện, không tràn ngang', async ({page}) => {
        await page.setViewportSize({width: 720, height: 900});
        await page.goto('/');
        await expect(page.locator('aside')).toBeHidden();
        await expect(page.getByRole('button', {name: 'Mở menu'})).toBeVisible();

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
        // `getByText` với string là case-insensitive + substring ⇒ phải `exact` + scope, nếu không khớp cả câu hỏi trong khung chat (strict mode)
        await expect(page.locator('aside').getByText('Kiểm tra F5', {exact: true})).toBeVisible();
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
