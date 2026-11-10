/**
 * KB-9.4: panel cấu hình runtime — dựng control từ `GET /settings`, lưu qua `PUT /settings`.
 */
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const api = vi.hoisted(() => ({
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    resetSettings: vi.fn(),
}));

vi.mock('@/lib/api', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@/lib/api')>();
    return {...actual, ...api};
});

import {SettingsPanel} from '@/components/settings-panel';

const RESPONSE = {
    values: {relevance_min_score: 0.02, retrieval_k: 6, enable_rerank: true, default_max_tokens: 2500},
    defaults: {relevance_min_score: 0.02, retrieval_k: 6, enable_rerank: true, default_max_tokens: 2500},
    overridden: [],
    tunables: [
        {key: 'relevance_min_score', kind: 'float' as const, min: 0, max: 0.5, description: 'ngưỡng'},
        {key: 'retrieval_k', kind: 'int' as const, min: 1, max: 12, description: 'k'},
        {key: 'enable_rerank', kind: 'bool' as const, min: null, max: null, description: 'rerank'},
        {key: 'default_max_tokens', kind: 'int' as const, min: 256, max: 8000, description: 'tokens'},
    ],
};

describe('SettingsPanel (KB-9.4)', () => {
    beforeEach(() => {
        api.getSettings.mockReset().mockResolvedValue(structuredClone(RESPONSE));
        api.updateSettings.mockReset().mockImplementation(async (values: Record<string, unknown>) => ({
            values: {...RESPONSE.values, ...values},
            overridden: Object.keys(values),
        }));
        api.resetSettings.mockReset().mockResolvedValue({values: RESPONSE.values, overridden: []});
    });

    it('dựng control từ `tunables` của BE và hiện giá trị server', async () => {
        render(<SettingsPanel/>);

        await waitFor(() => expect(screen.getByTestId('settings-panel')).toBeInTheDocument());
        expect(screen.getByLabelText(/Ngưỡng liên quan/)).toHaveValue(0.02);
        expect(screen.getByLabelText(/Số chunk đưa vào prompt/)).toHaveValue(6);
        expect(screen.getByLabelText(/Bật rerank/)).toBeChecked();
        expect(screen.getByTestId('settings-state')).toHaveTextContent('đang dùng mặc định');
    });

    it('sửa ⇒ nút Lưu bật và gửi **đúng tham số đã đổi**', async () => {
        render(<SettingsPanel/>);
        await waitFor(() => expect(screen.getByTestId('settings-panel')).toBeInTheDocument());

        const save = screen.getByRole('button', {name: /Lưu/});
        expect(save).toBeDisabled();

        const input = screen.getByLabelText(/Ngưỡng liên quan/);
        await userEvent.clear(input);
        await userEvent.type(input, '0.05');
        await expect(save).toBeEnabled();

        await userEvent.click(save);
        await waitFor(() => expect(api.updateSettings).toHaveBeenCalledWith({relevance_min_score: 0.05}));
        expect(screen.getByText('Đã lưu')).toBeInTheDocument();
    });

    it('"Mặc định" gọi reset và xoá badge đã đổi', async () => {
        api.getSettings.mockResolvedValueOnce({...structuredClone(RESPONSE), overridden: ['retrieval_k']});
        render(<SettingsPanel/>);
        await waitFor(() => expect(screen.getByTestId('settings-state')).toHaveTextContent('1 tham số đã đổi'));

        await userEvent.click(screen.getByRole('button', {name: /Mặc định/}));
        await waitFor(() => expect(api.resetSettings).toHaveBeenCalledOnce());
        expect(screen.getByTestId('settings-state')).toHaveTextContent('đang dùng mặc định');
    });

    it('lỗi khi tải ⇒ báo qua `onError`, không crash', async () => {
        api.getSettings.mockRejectedValueOnce(new Error('boom'));
        const onError = vi.fn();
        render(<SettingsPanel onError={onError}/>);

        await waitFor(() => expect(onError).toHaveBeenCalled());
    });
});
