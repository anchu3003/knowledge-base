import {expect, test} from '@playwright/test';

/**
 * KB-9.4: cấu hình runtime đọc từ `GET /settings` + ghi chú "đã bỏ N nguồn" (chạy trên BE thật).
 */
test.describe('KB-9.4 — cấu hình runtime & ngưỡng liên quan', () => {
    test('drawer hiện panel "Cấu hình server" với ngưỡng liên quan từ BE', async ({page}) => {
        await page.goto('/');
        await page.getByRole('button', {name: 'Kho tài liệu'}).click();

        const panel = page.getByTestId('settings-panel');
        await expect(panel).toBeVisible({timeout: 15_000});
        await expect(page.getByLabel(/Ngưỡng liên quan/)).toHaveValue('0.02');
        await expect(page.getByLabel(/Số chunk đưa vào prompt/)).toHaveValue('6');
        await expect(page.getByTestId('settings-state')).toContainText('mặc định');

        // Layout: input phải NẰM TRONG khung panel (đã từng bị label dài đẩy input ra ngoài drawer)
        const panelBox = await panel.boundingBox();
        const inputBox = await page.getByLabel(/Ngưỡng liên quan/).boundingBox();
        expect(panelBox && inputBox).toBeTruthy();
        expect(inputBox!.x).toBeGreaterThanOrEqual(panelBox!.x - 1);
        expect(inputBox!.x + inputBox!.width).toBeLessThanOrEqual(panelBox!.x + panelBox!.width + 1);

        await panel.screenshot({path: 'test-results/shot-18-settings-panel.png'});
    });

    test('đổi ngưỡng: Lưu gọi PUT, badge "đã đổi" hiện, "Mặc định" reset lại', async ({page}) => {
        const puts: Array<Record<string, unknown>> = [];
        page.on('request', (request) => {
            if (request.method() === 'PUT' && request.url().endsWith('/settings')) {
                puts.push(JSON.parse(request.postData() || '{}'));
            }
        });

        await page.goto('/');
        await page.getByRole('button', {name: 'Kho tài liệu'}).click();
        await expect(page.getByTestId('settings-panel')).toBeVisible({timeout: 15_000});

        const input = page.getByLabel(/Ngưỡng liên quan/);
        await input.fill('0.05');
        await page.getByRole('button', {name: /Lưu/}).click();
        await expect.poll(() => puts.length).toBeGreaterThan(0);
        expect(puts[0]).toEqual({relevance_min_score: 0.05});
        await expect(page.getByTestId('settings-state')).toContainText('1 tham số đã đổi');

        await page.getByRole('button', {name: /Mặc định/}).click();
        await expect(page.getByTestId('settings-state')).toContainText('mặc định');
        await expect(input).toHaveValue('0.02');
    });
});
