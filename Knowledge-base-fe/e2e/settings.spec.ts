import {expect, test} from '@playwright/test';

/**
 * KB-9.4 + KB-9.6: cấu hình runtime nằm **trong panel "Tuỳ chọn"** của composer (một chỗ duy nhất),
 * đọc từ `GET /settings` của BE thật.
 */
async function openSettings(page: import('@playwright/test').Page) {
    await page.goto('/');
    await page.getByRole('button', {name: /Tuỳ chọn/i}).click();
    const panel = page.getByTestId('settings-panel');
    await expect(panel).toBeVisible({timeout: 15_000});
    return panel;
}

test.describe('KB-9.4/9.6 — cấu hình runtime trong Tuỳ chọn', () => {
    test('12 tham số server hiện trong panel Tuỳ chọn, đúng giá trị BE', async ({page}) => {
        const panel = await openSettings(page);

        await expect(page.getByLabel(/Ngưỡng liên quan/)).toHaveValue('0.02');
        await expect(page.getByLabel(/Số chunk đưa vào prompt/)).toHaveValue('6');
        await expect(page.getByLabel(/Số ứng viên rerank/)).toHaveValue('6');
        await expect(page.getByLabel(/Bật rerank/)).toBeChecked();
        // 12 tunable: đếm control sinh ra từ `tunables`
        const rows = panel.locator('div.flex.min-w-0.items-center.justify-between');
        expect(await rows.count()).toBe(12);
        await expect(page.getByTestId('settings-state')).toContainText('mặc định');

        // Layout: input phải NẰM TRONG khung panel (đã từng bị label dài đẩy ra ngoài)
        const panelBox = await panel.boundingBox();
        const inputBox = await page.getByLabel(/Ngưỡng liên quan/).boundingBox();
        expect(panelBox && inputBox).toBeTruthy();
        expect(inputBox!.x).toBeGreaterThanOrEqual(panelBox!.x - 1);
        expect(inputBox!.x + inputBox!.width).toBeLessThanOrEqual(panelBox!.x + panelBox!.width + 1);

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

