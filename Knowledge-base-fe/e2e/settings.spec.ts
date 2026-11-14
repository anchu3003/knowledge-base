import {expect, test} from '@playwright/test';

/**
 * KB-9.4 + KB-9.6: cấu hình runtime nằm **trong panel "Tuỳ chọn"** của composer (một chỗ duy nhất),
 * cùng khuôn với 2 control per-request; 2 tham số trùng default bị ẩn.
 */
async function openSettings(page: import('@playwright/test').Page) {
    await page.goto('/');
    await page.getByRole('button', {name: /Tuỳ chọn/i}).click();
    const panel = page.getByTestId('settings-panel');
    await expect(panel).toBeVisible({timeout: 15_000});
    return panel;
}

test.describe('KB-9.4/9.6 — cấu hình runtime trong Tuỳ chọn', () => {
    test('panel cấu hình cùng khuôn, không trùng field, đúng giá trị BE', async ({page}) => {
        const panel = await openSettings(page);

        // Giá trị lấy từ BE
        await expect(page.getByLabel(/Ngưỡng liên quan/)).toHaveValue('0.02');
        await expect(page.getByLabel(/Số chunk đưa vào prompt/)).toHaveValue('6');
        await expect(page.getByLabel(/Số ứng viên rerank/)).toHaveValue('6');

        // KHÔNG còn field trùng với 2 control phía trên (default_temperature / default_max_tokens)
        await expect(panel.getByText('Temperature mặc định')).toHaveCount(0);
        await expect(panel.getByText('max_tokens mặc định')).toHaveCount(0);

        // 12 tunable − 2 field trùng = 10 control (7 số + 3 checkbox)
        expect(await panel.locator('input[type="number"]').count()).toBe(7);
        expect(await panel.locator('input[type="checkbox"]').count()).toBe(3);

        // Label của 2 control per-request hiện default server thay vì field trùng
        await expect(page.getByText(/auto \(server: 0\.2\)/)).toBeVisible();
        await expect(page.getByPlaceholder(/auto \(2500\)/)).toBeVisible();

        // Layout: mọi input nằm trong khung panel
        const panelBox = await panel.boundingBox();
        for (const label of [/Ngưỡng liên quan/, /Số chunk đưa vào prompt/]) {
            const box = await page.getByLabel(label).boundingBox();
            expect(box && panelBox).toBeTruthy();
            expect(box!.x).toBeGreaterThanOrEqual(panelBox!.x - 1);
            expect(box!.x + box!.width).toBeLessThanOrEqual(panelBox!.x + panelBox!.width + 1);
        }

        await panel.screenshot({path: 'test-results/shot-18-settings-panel.png'});
    });

    test('đổi ngưỡng: Lưu gọi PUT, badge "đã đổi", "Mặc định" reset lại', async ({page}) => {
        const puts: Array<Record<string, unknown>> = [];
        page.on('request', (request) => {
            if (request.method() === 'PUT' && request.url().endsWith('/settings')) {
                puts.push(JSON.parse(request.postData() || '{}'));
            }
        });

        await openSettings(page);

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


