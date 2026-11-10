import {expect, test} from '@playwright/test';

/**
 * KB-9.2: tham số trả lời trên UI thật — mặc định "theo server" (không gửi field), chỉnh thì gửi kèm
 * và **được lưu** (F5 vẫn còn).
 */
test.describe('Tham số trả lời (KB-9.2)', () => {
    test('mặc định theo server → chỉnh max tokens/temperature → request gửi kèm và lưu qua F5', async ({page}) => {
        const bodies: Array<Record<string, unknown>> = [];
        // Chặn SSE thật: chỉ cần kiểm body request, không cần BE trả lời
        await page.route('**/chat/stream', async (route) => {
            bodies.push(JSON.parse(route.request().postData() || '{}'));
            await route.fulfill({
                status: 200,
                headers: {'content-type': 'text/event-stream', 'cache-control': 'no-cache'},
                body:
                    'data: {"type":"start","conversation_id":"c1"}\n\n' +
                    'data: {"type":"token","token":"ok"}\n\n' +
                    'data: {"type":"end","sources":[]}\n\n',
            });
        });

        await page.goto('/');
        await page.getByRole('button', {name: /Tuỳ chọn/i}).click();

        // 1) Mặc định: "theo server" ⇒ body KHÔNG có max_tokens/temperature
        await expect(page.getByText('theo server', {exact: true})).toBeVisible();
        await expect(page.getByLabel('Max tokens')).toHaveAttribute('placeholder', 'auto (server)');

        await page.getByRole('textbox').first().fill('Saga là gì?');
        await page.getByRole('button', {name: /Gửi|Tạo mới/i}).first().click();
        await expect.poll(() => bodies.length).toBeGreaterThan(0);
        expect(bodies[0].max_tokens).toBeUndefined();
        expect(bodies[0].temperature).toBeUndefined();

        // 2) Chỉnh max tokens ⇒ chỉ field đó được gửi (temperature vẫn "theo server")
        await page.getByLabel('Max tokens').fill('3000');
        await expect(page.getByText('theo server', {exact: true})).toBeHidden();
        await page.getByRole('textbox').first().fill('Kafka ordering?');
        await page.getByRole('button', {name: /Gửi|Tạo mới/i}).first().click();
        await expect.poll(() => bodies.length).toBeGreaterThan(1);
        expect(bodies[1].max_tokens).toBe(3000);
        expect(bodies[1].temperature).toBeUndefined();

        // 3) Lưu qua F5 (localStorage): giá trị còn nguyên
        await page.reload();
        await page.getByRole('button', {name: /Tuỳ chọn/i}).click();
        await expect(page.getByLabel('Max tokens')).toHaveValue('3000');

        // 4) Có temperature đã lưu (slider Radix khó kéo bằng Playwright ⇒ set qua localStorage
        //    rồi reload — kiểm đúng thứ cần kiểm: giá trị đã lưu được gửi kèm request)
        await page.evaluate(() => {
            window.localStorage.setItem('kb.answer.v1', JSON.stringify({maxTokens: 3000, temperature: 0.5}));
        });
        await page.reload();
        await page.getByRole('button', {name: /Tuỳ chọn/i}).click();
        await expect(page.getByText(/Temperature: 0\.50/)).toBeVisible();
        await page.getByRole('textbox').first().fill('Khi nào dùng index?');
        await page.getByRole('button', {name: /Gửi|Tạo mới/i}).first().click();
        await expect.poll(() => bodies.length).toBeGreaterThan(2);
        expect(bodies[2].max_tokens).toBe(3000);
        expect(bodies[2].temperature).toBe(0.5);

        // 5) "Dùng theo server" ⇒ về null cả 2
        await page.getByRole('button', {name: /Dùng theo server/i}).click();
        await expect(page.getByLabel('Max tokens')).toHaveValue('');
        await expect(page.getByText('theo server', {exact: true})).toBeVisible();
    });
});


