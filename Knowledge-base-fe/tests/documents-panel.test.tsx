import {describe, expect, it, vi} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
    CLEAR_CONFIRM_WORD,
    DocumentsPanelContent,
    canConfirmClear,
    failedChecks,
    isSyncSafe,
    readyTone,
    syncBlockedReason,
} from '@/components/documents-panel';

const baseProps = {
    status: {collection_name: 'kb_documents', document_count: 128, status: 'healthy'},
    folder: {folder_path: '/srv/docs', exists: true, total_files: 7, supported_files_count: 6},
    ready: {status: 'ok', checks: {provider_config: {ok: true, detail: 'model=gpt-4o-mini'}}},
    loading: false,
    loadError: null,
    actionError: null,
    busy: null,
    pending: null,
    syncResult: null,
    cleared: false,
    clearInput: '',
    onReload: vi.fn(),
    onClose: vi.fn(),
    onSync: vi.fn(),
    onCheckProvider: vi.fn(),
    onAskClear: vi.fn(),
    onCancel: vi.fn(),
    onConfirmClear: vi.fn(),
    onClearInputChange: vi.fn(),
    onSettingsError: vi.fn(),
} as const;

describe('DocumentsPanelContent (KB-4.5)', () => {
    it('hiện số chunk, collection, file trong folder', () => {
        render(<DocumentsPanelContent {...baseProps}/>);

        expect(screen.getByText('Chunk đã index')).toBeInTheDocument();
        expect(screen.getByText('128')).toBeInTheDocument();
        expect(screen.getByText('kb_documents')).toBeInTheDocument();
        expect(screen.getByText('7')).toBeInTheDocument();
    });

    it('/ready = error ⇒ badge lỗi + tên check fail, chỉ rõ lý do', () => {
        const onCheckProvider = vi.fn();
        render(<DocumentsPanelContent {...baseProps} onCheckProvider={onCheckProvider} ready={{
            status: 'error',
            checks: {
                provider_config: {ok: false, detail: 'missing config: OPENAI_API_KEY'},
                collection: {ok: true, detail: '128 chunks indexed'},
            },
        }}/>);

        expect(screen.getByText(/Có check lỗi/)).toBeInTheDocument();
        expect(screen.getByTestId('ready-check-provider_config')).toHaveTextContent('✗ provider_config');
        expect(screen.getByText(/: missing config: OPENAI_API_KEY/)).toBeInTheDocument();
        // TD-23: check ok cũng hiện (để thấy startup_sync / rate_limit) nhưng đánh dấu ✓
        expect(screen.getByTestId('ready-check-collection')).toHaveTextContent('✓ collection');
    });

    it('TD-23: hiện mọi check gồm startup_sync + rate_limit từ BE', () => {
        render(<DocumentsPanelContent {...baseProps} ready={{
            status: 'ok',
            checks: {
                provider_config: {ok: true, detail: 'model=gpt-4o-mini'},
                startup_sync: {ok: true, detail: 'index sync xong trong 1.2s (+0 mới, 601 chunk)'},
                rate_limit: {ok: true, detail: 'rate limit tắt (RATE_LIMIT_ENABLED=false)'},
            },
        }}/>);

        expect(screen.getByTestId('ready-check-startup_sync')).toHaveTextContent('601 chunk');
        expect(screen.getByTestId('ready-check-rate_limit')).toHaveTextContent('RATE_LIMIT_ENABLED');
        expect(screen.queryByText(/Có check lỗi/)).toBeNull();
    });

    it('TD-23: bấm "Kiểm tra provider" gọi handler, đang kiểm thì disable', async () => {
        const onCheckProvider = vi.fn();
        const {rerender} = render(<DocumentsPanelContent {...baseProps} onCheckProvider={onCheckProvider}/>);

        await userEvent.click(screen.getByRole('button', {name: /Kiểm tra provider/i}));
        expect(onCheckProvider).toHaveBeenCalledOnce();

        rerender(<DocumentsPanelContent {...baseProps} busy="check" onCheckProvider={onCheckProvider}/>);
        const checking = screen.getByRole('button', {name: /Đang kiểm/i});
        expect(checking).toBeDisabled();
    });

    it('lỗi tải dữ liệu ⇒ banner đúng contract KB-4.1 (code + request_id)', () => {
        render(<DocumentsPanelContent {...baseProps} loadError={{
            code: 'document_store_error',
            message: 'Backend gặp lỗi khi đọc/ghi kho tài liệu.',
            hint: 'Thử lại.',
            requestId: 'req-9',
            retryable: false,
        }}/>);

        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/code=document_store_error/)).toBeInTheDocument();
        expect(screen.getByText(/request_id=req-9/)).toBeInTheDocument();
    });

    it('pending clear ⇒ nút xác nhận bị khoá cho tới khi gõ đúng CLEAR', async () => {
        const onConfirmClear = vi.fn();
        const {rerender} = render(
            <DocumentsPanelContent {...baseProps} pending="clear" onConfirmClear={onConfirmClear}/>
        );

        const confirmButton = screen.getByRole('button', {name: 'Xác nhận xoá index'});
        expect(confirmButton).toBeDisabled();

        // giả lập người dùng đã gõ đúng từ khoá (state do container giữ)
        rerender(<DocumentsPanelContent {...baseProps} pending="clear" clearInput={CLEAR_CONFIRM_WORD}
                                         onConfirmClear={onConfirmClear}/>);
        await userEvent.click(screen.getByRole('button', {name: 'Xác nhận xoá index'}));

        expect(onConfirmClear).toHaveBeenCalledOnce();
    });

    it('đồng bộ xong ⇒ hiện số mới/cập nhật/xoá + thời gian (KB-5.1)', () => {
        render(<DocumentsPanelContent {...baseProps} syncResult={{
            success: true,
            message: '+1 mới, ~1 cập nhật, -1 xoá',
            added: ['moi.md'],
            updated: ['sua.md'],
            removed: ['da-xoa.md'],
            skipped: [{path: '/docs/big.md', reason: 'too_large: 12.0MB > 10MB'}],
            unchanged: 4,
            total_chunks: 6,
            removed_chunks: 3,
            elapsed_ms: 1234,
        }}/>);

        const result = screen.getByTestId('sync-result');
        expect(result).toHaveTextContent('1 mới');
        expect(result).toHaveTextContent('1 cập nhật');
        expect(result).toHaveTextContent('1 xoá');
        expect(result).toHaveTextContent('4 không đổi');
        expect(result).toHaveTextContent('1 bỏ qua');
        expect(result).toHaveTextContent('6 chunk mới');
        expect(result).toHaveTextContent('1.2s');
        // file bị bỏ qua phải nêu lý do (để user biết vì sao không thấy tài liệu đó)
        expect(result).toHaveTextContent('big.md');
        expect(result).toHaveTextContent('too_large');
    });

    it('bấm "Đồng bộ file mới" / "Clear" ⇒ gọi callback tương ứng', async () => {
        const onSync = vi.fn();
        const onAskClear = vi.fn();
        render(<DocumentsPanelContent {...baseProps} onSync={onSync} onAskClear={onAskClear}/>);

        await userEvent.click(screen.getByRole('button', {name: /Đồng bộ file mới/}));
        await userEvent.click(screen.getByRole('button', {name: /^Clear$/}));

        expect(onSync).toHaveBeenCalledOnce();
        expect(onAskClear).toHaveBeenCalledOnce();
    });
});

describe('helpers của DocumentsPanel', () => {
    it('readyTone: giá trị lạ ⇒ unknown (không crash)', () => {
        expect(readyTone('ok')).toBe('ok');
        expect(readyTone('degraded')).toBe('degraded');
        expect(readyTone('weird')).toBe('unknown');
        expect(readyTone(undefined)).toBe('unknown');
    });

    it('failedChecks chỉ trả check ok=false', () => {
        const failures = failedChecks({
            status: 'error',
            checks: {
                a: {ok: false, detail: 'x'},
                b: {ok: true, detail: 'y'},
            },
        });

        expect(failures).toEqual([{name: 'a', detail: 'x'}]);
        expect(failedChecks(null)).toEqual([]);
    });

    it('canConfirmClear so khớp chính xác', () => {
        expect(canConfirmClear('CLEAR')).toBe(true);
        expect(canConfirmClear('clear')).toBe(false);
        expect(canConfirmClear('CLEAR ')).toBe(false);
    });
});

// KB-4.10: Refresh phải bị chặn khi backend không thấy folder tài liệu (nếu không sẽ xoá index vô ích)
describe('Refresh bị chặn khi folder tài liệu rỗng (KB-4.10)', () => {
    it('folder không tồn tại ⇒ nút Refresh disabled + hiện lý do', () => {
        const onSync = vi.fn();
        render(<DocumentsPanelContent {...baseProps}
                                     folder={{...baseProps.folder, exists: false, supported_files_count: 0}}
                                     onSync={onSync}/>);

        const syncButton = screen.getByRole('button', {name: /Đồng bộ file mới/});
        expect(syncButton).toBeDisabled();
        expect(screen.getByRole('status')).toHaveTextContent(/không thấy folder tài liệu/i);
    });

    it('folder có nhưng 0 file hỗ trợ ⇒ cũng chặn', () => {
        render(<DocumentsPanelContent {...baseProps}
                                     folder={{...baseProps.folder, exists: true, supported_files_count: 0}}/>);

        expect(screen.getByRole('button', {name: /Đồng bộ file mới/})).toBeDisabled();
        expect(screen.getByRole('status')).toHaveTextContent(/không có file hỗ trợ/i);
    });

    it('folder có file hỗ trợ ⇒ Refresh bật bình thường', async () => {
        const onSync = vi.fn();
        render(<DocumentsPanelContent {...baseProps}
                                     folder={{...baseProps.folder, exists: true, supported_files_count: 6}}
                                     onSync={onSync}/>);

        const syncButton = screen.getByRole('button', {name: /Đồng bộ file mới/});
        expect(syncButton).toBeEnabled();
        expect(screen.queryByRole('status')).toBeNull();
        await userEvent.click(syncButton);
        expect(onSync).toHaveBeenCalledOnce();
    });

    it('helpers: isSyncSafe / syncBlockedReason', () => {
        expect(isSyncSafe(null)).toBe(false);
        expect(isSyncSafe({exists: false} as never)).toBe(false);
        expect(isSyncSafe({exists: true, supported_files_count: 0} as never)).toBe(false);
        expect(isSyncSafe({exists: true, supported_files_count: 3} as never)).toBe(true);
        expect(syncBlockedReason({exists: true, supported_files_count: 3} as never)).toBeNull();
    });
});
