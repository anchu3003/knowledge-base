/**
 * KB-9.2: control tham số trong composer — `null` = theo server.
 */
import {describe, expect, it, vi} from 'vitest';
import {useState} from 'react';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {ChatComposer} from '@/components/chat-composer';

const baseProps = {
    value: 'Saga là gì?',
    onChange: vi.fn(),
    onSend: vi.fn(),
    isLoading: false,
    streamingEnabled: true,
    formError: null,
    maxTokensLimit: {min: 200, max: 4000},
};

async function openAdvanced() {
    await userEvent.click(screen.getByRole('button', {name: /Tuỳ chọn/i}));
}

/** Wrapper có state — mô phỏng `page.tsx` (component là controlled). */
function Harness({initialMax = null as number | null, initialTemp = null as number | null,
                  onMaxTokensChange = vi.fn() as (v: number | null) => void,
                  onUseServerDefaults = vi.fn()}) {
    const [maxTokens, setMaxTokens] = useState<number | null>(initialMax);
    const [temperature, setTemperature] = useState<number | null>(initialTemp);
    return (
        <ChatComposer
            {...baseProps}
            maxTokens={maxTokens}
            onMaxTokensChange={(v) => {
                setMaxTokens(v);
                onMaxTokensChange(v);
            }}
            temperature={temperature}
            onTemperatureChange={setTemperature}
            usingServerDefaults={maxTokens === null && temperature === null}
            onUseServerDefaults={() => {
                setMaxTokens(null);
                setTemperature(null);
                onUseServerDefaults();
            }}
        />
    );
}

describe('ChatComposer — tham số trả lời (KB-9.2)', () => {
    it('"theo server": ô max tokens rỗng + placeholder auto, có badge', async () => {
        render(<Harness/>);
        await openAdvanced();

        const input = screen.getByLabelText('Max tokens');
        expect(input).toHaveValue(null);
        expect(input).toHaveAttribute('placeholder', 'auto (server)');
        expect(screen.getByText('theo server')).toBeInTheDocument();
        expect(screen.getByText(/Temperature: auto \(server\)/)).toBeInTheDocument();
    });

    it('nhập số ⇒ callback nhận number; xoá trắng ⇒ callback nhận null', async () => {
        const onMaxTokensChange = vi.fn();
        render(<Harness onMaxTokensChange={onMaxTokensChange}/>);
        await openAdvanced();

        const input = screen.getByLabelText('Max tokens');
        await userEvent.type(input, '3000');
        expect(onMaxTokensChange).toHaveBeenLastCalledWith(3000);
        expect(input).toHaveValue(3000);

        await userEvent.clear(input);
        expect(onMaxTokensChange).toHaveBeenLastCalledWith(null);
    });

    it('hiện giá trị đang dùng và nút "Dùng theo server" trả về null', async () => {
        const onUseServerDefaults = vi.fn();
        render(<Harness initialMax={1500} initialTemp={0} onUseServerDefaults={onUseServerDefaults}/>);
        await openAdvanced();

        expect(screen.getByLabelText('Max tokens')).toHaveValue(1500);
        expect(screen.getByText(/Temperature: 0\.00/)).toBeInTheDocument();

        await userEvent.click(screen.getByRole('button', {name: /Dùng theo server/i}));
        expect(onUseServerDefaults).toHaveBeenCalledOnce();
        expect(screen.getByLabelText('Max tokens')).toHaveValue(null);
    });
});

