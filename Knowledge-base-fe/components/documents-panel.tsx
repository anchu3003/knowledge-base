'use client';

/**
 * Panel trạng thái kho tài liệu + provider (KB-4.5) — mở từ header dưới dạng drawer.
 *
 * - Chỉ fetch khi mở (giả định (a) của ticket) — không poll.
 * - `/documents/status` (số chunk) + `/documents/folder-info` (đếm file trên đĩa) + `/ready` (provider/config).
 * - **Đồng bộ file mới** (KB-5.1): index tăng dần — chỉ file mới/đổi, xoá chunk của file đã bỏ. Không clear
 *   index ⇒ chat vẫn dùng được trong lúc sync. Nút **Refresh toàn bộ** đã bỏ (Q&A Q3 = B).
 * - **Clear**: xoá sạch index ⇒ Q&A KB-4.5 Q2 chốt: phải **gõ `CLEAR`** mới bấm được.
 * - Lỗi hiện theo contract KB-4.1 (`describeApiError`: code + message + hint + request_id).
 *
 * Tách `DocumentsPanelContent` (thuần props) khỏi `DocumentsPanel` (fetch/state) để verify được bằng SSR.
 */

import {useCallback, useEffect, useState} from 'react';
import {
    clearDocuments,
    getDocumentsStatus,
    getFolderInfo,
    getReady,
    syncDocuments,
} from '@/lib/api';
import {describeApiError, type ApiErrorView} from '@/lib/errors';
import type {
    DocumentStatus,
    DocumentsSyncResult,
    FolderInfo,
    ReadinessStatus,
} from '@/lib/types';
import {Button} from '@/components/ui/button';
import {Sheet, SheetContent, SheetTitle} from '@/components/ui/sheet';
import {CheckCircle2, Database, RefreshCw, Trash2, X, XCircle} from 'lucide-react';

/** Từ khoá phải gõ để xác nhận xoá index (Q&A KB-4.5 Q2). */
export const CLEAR_CONFIRM_WORD = 'CLEAR';

export type ReadyTone = 'ok' | 'degraded' | 'error' | 'unknown';

/** `status` của `/ready` → tone hiển thị (giá trị lạ ⇒ `unknown`, **không** crash). */
export function readyTone(status?: string): ReadyTone {
    if (status === 'ok' || status === 'degraded' || status === 'error') return status;
    return 'unknown';
}

/** Class Tailwind cho badge readiness. */
export function readyToneClasses(tone: ReadyTone): string {
    switch (tone) {
        case 'ok':
            return 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700/60 dark:bg-emerald-900/20 dark:text-emerald-300';
        case 'degraded':
            return 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700/60 dark:bg-amber-900/20 dark:text-amber-300';
        case 'error':
            return 'border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-700/60 dark:bg-rose-900/20 dark:text-rose-300';
        default:
            return 'border-slate-300 bg-slate-50 text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300';
    }
}

/** Nhãn tiếng Việt cho trạng thái readiness. */
export function readyLabel(tone: ReadyTone): string {
    switch (tone) {
        case 'ok':
            return 'Sẵn sàng';
        case 'degraded':
            return 'Thiếu tài liệu (vẫn trả lời được)';
        case 'error':
            return 'Có check lỗi — chưa trả lời được';
        default:
            return 'Không rõ';
    }
}

/** Các check `ok === false` (tên + detail) để hiện lý do, không chỉ badge đỏ. */
export function failedChecks(ready?: ReadinessStatus | null): Array<{name: string; detail: string}> {
    if (!ready || !ready.checks) return [];
    return Object.entries(ready.checks)
        .filter(([, check]) => check && check.ok === false)
        .map(([name, check]) => ({name, detail: check.detail || ''}));
}

/** Nút Clear chỉ bấm được khi gõ đúng từ khoá (so khớp chính xác, không trim hoa thường). */
export function canConfirmClear(input: string): boolean {
    return input === CLEAR_CONFIRM_WORD;
}

/**
 * Sync đối chiếu folder với index ⇒ nếu backend **không thấy folder** (không tồn tại hoặc 0 file hỗ trợ) thì
 * mọi file đang index sẽ bị coi là "đã xoá" và **bị xoá khỏi vector store** ⇒ phải chặn ở UI
 * (cùng lý do với KB-4.10, giờ áp cho sync).
 */
export function isSyncSafe(folder?: FolderInfo | null): boolean {
    if (!folder) return false;
    if (folder.exists === false) return false;
    return (folder.supported_files_count ?? 0) > 0;
}

/** Lý do nút Đồng bộ bị chặn (hiện cạnh nút) — `null` khi an toàn. */
export function syncBlockedReason(folder?: FolderInfo | null): string | null {
    if (!folder) return 'Chưa đọc được thông tin folder tài liệu.';
    if (folder.exists === false) {
        return `Backend không thấy folder tài liệu (${folder.folder_path}) — đồng bộ sẽ coi mọi tài liệu đã index là "đã xoá" và xoá khỏi index.`;
    }
    if ((folder.supported_files_count ?? 0) === 0) {
        return 'Folder tài liệu không có file hỗ trợ nào — đồng bộ sẽ xoá toàn bộ index hiện có.';
    }
    return null;
}

// ------------------------------
// Presentational — nhận toàn bộ data qua props (SSR test được)
// ------------------------------

export interface DocumentsPanelContentProps {
    status: DocumentStatus | null;
    folder: FolderInfo | null;
    ready: ReadinessStatus | null;
    loading: boolean;
    /** Lỗi khi tải trạng thái (banner KB-4.1). */
    loadError: ApiErrorView | null;
    /** Lỗi của Đồng bộ/Clear. */
    actionError: ApiErrorView | null;
    /** Hành động đang chạy. */
    busy: 'sync' | 'clear' | null;
    /** Hành động đang chờ xác nhận (chỉ Clear cần — sync không phá huỷ). */
    pending: 'clear' | null;
    syncResult: DocumentsSyncResult | null;
    cleared: boolean;
    clearInput: string;
    onReload: () => void;
    onClose: () => void;
    onSync: () => void;
    onAskClear: () => void;
    onCancel: () => void;
    onConfirmClear: () => void;
    onClearInputChange: (value: string) => void;
}

/** Banner lỗi theo đúng format KB-4.1 (`code` + message + hint + `request_id`). */
function ErrorBox({view}: {view: ApiErrorView}) {
    return (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-800/60 dark:bg-rose-900/20 dark:text-rose-200">
            <p className="font-semibold">{view.message}</p>
            {view.hint && <p className="mt-1 opacity-90">{view.hint}</p>}
            <p className="mt-1 font-mono opacity-80">
                code={view.code} · request_id={view.requestId}
            </p>
        </div>
    );
}

function StatRow({label, value, hint}: {label: string; value: string; hint?: string}) {
    return (
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 py-2 last:border-0 dark:border-slate-700/60">
            <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
            <span className="text-right text-xs font-medium text-slate-800 dark:text-slate-100">
                {value}
                {hint && <span className="ml-1 font-normal text-slate-400 dark:text-slate-500">({hint})</span>}
            </span>
        </div>
    );
}


export function DocumentsPanelContent({
                                           status,
                                           folder,
                                           ready,
                                           loading,
                                           loadError,
                                           actionError,
                                           busy,
                                           pending,
                                           syncResult,
                                           cleared,
                                           clearInput,
                                           onReload,
                                           onClose,
                                           onSync,
                                           onAskClear,
                                           onCancel,
                                           onConfirmClear,
                                           onClearInputChange,
                                       }: DocumentsPanelContentProps) {
    const tone = readyTone(ready?.status);
    const failures = failedChecks(ready);
    const disabled = busy !== null;
    // KB-4.10: chặn Refresh khi backend không thấy folder tài liệu (sẽ xoá index mà không index lại được)
    const syncBlocked = syncBlockedReason(folder);

    return (
        <div className="flex h-full flex-col">
            <header className="flex items-center justify-between border-b border-border px-4 py-3">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Database className="h-4 w-4 text-primary"/>
                    Kho tài liệu
                </h2>
                <div className="flex items-center gap-1">
                    <button type="button" onClick={onReload} disabled={loading || disabled}
                            aria-label="Tải lại trạng thái"
                            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted disabled:opacity-40">
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`}/>
                    </button>
                    <button type="button" onClick={onClose} aria-label="Đóng"
                            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted">
                        <X className="h-4 w-4"/>
                    </button>
                </div>
            </header>

                <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3">
                    {loadError && <ErrorBox view={loadError}/>}

                    {loading && (
                        <p className="text-xs text-slate-500 dark:text-slate-400">Đang tải trạng thái…</p>
                    )}

                    {status && (
                        <section>
                            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                                Index
                            </h3>
                            <StatRow label="Chunk đã index" value={String(status.document_count)}/>
                            <StatRow label="Collection" value={status.collection_name}/>
                            <StatRow label="Trạng thái index" value={status.status}/>
                            {status.error && <StatRow label="Lỗi" value={status.error}/>}
                            {folder && (
                                <>
                                    <StatRow label="File trong folder" value={String(folder.total_files ?? 0)}
                                             hint={folder.exists ? undefined : 'folder không tồn tại'}/>
                                    <StatRow label="File hỗ trợ"
                                             value={String(folder.supported_files_count ?? 0)}
                                             hint={folder.auto_load_enabled ? 'auto-load bật' : 'auto-load tắt'}/>
                                    <StatRow label="Folder" value={folder.folder_path}/>
                                </>
                            )}
                        </section>
                    )}


                    {ready && (
                        <section>
                            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                                Readiness
                            </h3>
                            <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${readyToneClasses(tone)}`}>
                                {tone === 'ok'
                                    ? <CheckCircle2 className="h-3.5 w-3.5"/>
                                    : <XCircle className="h-3.5 w-3.5"/>}
                                {ready.status} — {readyLabel(tone)}
                            </span>
                            {failures.length > 0 && (
                                <ul className="mt-2 space-y-1">
                                    {failures.map((failure) => (
                                        <li key={failure.name}
                                            className="rounded-md bg-rose-50 px-2 py-1 text-xs text-rose-800 dark:bg-rose-900/20 dark:text-rose-200">
                                            <span className="font-mono font-semibold">{failure.name}</span>
                                            {failure.detail && <span className="opacity-90">: {failure.detail}</span>}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </section>
                    )}

                    {actionError && <ErrorBox view={actionError}/>}

                    {syncResult && (
                        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-900 dark:border-emerald-800/60 dark:bg-emerald-900/20 dark:text-emerald-200"
                             data-testid="sync-result">
                            <p className="font-semibold">
                                ✓ {syncResult.message}
                            </p>
                            <p className="mt-1">
                                {syncResult.added.length} mới · {syncResult.updated.length} cập nhật ·{' '}
                                {syncResult.removed.length} xoá · {syncResult.unchanged} không đổi
                                {syncResult.skipped.length > 0 && ` · ${syncResult.skipped.length} bỏ qua`}
                                {' '}· {syncResult.total_chunks} chunk mới · {(syncResult.elapsed_ms / 1000).toFixed(1)}s
                            </p>
                            {syncResult.skipped.length > 0 && (
                                <ul className="mt-1 list-disc pl-4">
                                    {syncResult.skipped.slice(0, 3).map((item) => (
                                        <li key={item.path} className="font-mono text-[11px]">
                                            {item.path.split(/[\\/]/).pop()}: {item.reason}
                                        </li>
                                    ))}
                                </ul>
                            )}
                            {syncResult.details && syncResult.details.length > 0 && (
                                <ul className="mt-1 list-disc pl-4">
                                    {syncResult.details.slice(0, 3).map((detail) => (
                                        <li key={detail} className="font-mono text-[11px]">{detail}</li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    )}

                    {cleared && (
                        <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-800 dark:border-emerald-800/60 dark:bg-emerald-900/20 dark:text-emerald-200">
                            ✓ Đã xoá index (file trên đĩa vẫn còn).
                        </p>
                    )}


                    {/* ----- Hành động: Clear (phải gõ CLEAR) ----- */}
                    {pending === 'clear' && (
                        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900 dark:border-rose-800/60 dark:bg-rose-900/20 dark:text-rose-200">
                            <p className="font-semibold">Clear sẽ xoá TOÀN BỘ index (file trên đĩa vẫn còn).</p>
                            <p className="mt-1">
                                Gõ <span className="font-mono font-semibold">{CLEAR_CONFIRM_WORD}</span> để bật nút xác nhận.
                            </p>
                            <input
                                value={clearInput}
                                onChange={(event) => onClearInputChange(event.target.value)}
                                disabled={disabled}
                                aria-label={`Gõ ${CLEAR_CONFIRM_WORD} để xác nhận xoá index`}
                                placeholder={CLEAR_CONFIRM_WORD}
                                className="mt-2 w-full rounded-md border border-rose-300 bg-white px-2 py-1 font-mono text-xs dark:border-rose-700/60 dark:bg-slate-900"
                            />
                            <div className="mt-2 flex gap-2">
                                <Button size="sm" onClick={onConfirmClear}
                                        disabled={disabled || !canConfirmClear(clearInput)}>
                                    {busy === 'clear' ? 'Đang xoá…' : 'Xác nhận xoá index'}
                                </Button>
                                <Button size="sm" variant="ghost" onClick={onCancel} disabled={disabled}>
                                    Huỷ
                                </Button>
                            </div>
                        </div>
                    )}
                </div>

                <footer className="flex flex-col gap-2 border-t border-slate-200 px-4 py-3 dark:border-slate-700">
                    {syncBlocked && (
                        <p role="status"
                           className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-900 dark:border-amber-800/60 dark:bg-amber-900/20 dark:text-amber-200">
                            ⚠ {syncBlocked}
                        </p>
                    )}
                    <div className="flex items-center justify-end gap-2">
                        <Button size="sm" onClick={onSync}
                                disabled={disabled || pending !== null || syncBlocked !== null}
                                title={syncBlocked ?? 'Index các file mới/đã sửa trong folder tài liệu (không xoá index cũ)'}
                                className="gap-1">
                            <RefreshCw className={`h-3.5 w-3.5 ${busy === 'sync' ? 'animate-spin' : ''}`}/>
                            {busy === 'sync' ? 'Đang đồng bộ…' : 'Đồng bộ file mới'}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={onAskClear}
                                disabled={disabled || pending !== null}
                                className="gap-1 text-rose-600 hover:text-rose-700 dark:text-rose-400">
                            <Trash2 className="h-3.5 w-3.5"/>
                            Clear
                        </Button>
                    </div>
                </footer>
        </div>
    );
}


// ------------------------------
// Container — fetch khi mở + chạy hành động
// ------------------------------

export interface DocumentsPanelProps {
    open: boolean;
    onClose: () => void;
}

export function DocumentsPanel({open, onClose}: DocumentsPanelProps) {
    const [status, setStatus] = useState<DocumentStatus | null>(null);
    const [folder, setFolder] = useState<FolderInfo | null>(null);
    const [ready, setReady] = useState<ReadinessStatus | null>(null);
    const [loading, setLoading] = useState(false);
    const [loadError, setLoadError] = useState<ApiErrorView | null>(null);
    const [actionError, setActionError] = useState<ApiErrorView | null>(null);
    const [busy, setBusy] = useState<'sync' | 'clear' | null>(null);
    const [pending, setPending] = useState<'clear' | null>(null);
    const [syncResult, setSyncResult] = useState<DocumentsSyncResult | null>(null);
    const [cleared, setCleared] = useState(false);
    const [clearInput, setClearInput] = useState('');

    /** Tải 3 nguồn song song; mỗi nguồn lỗi riêng ⇒ vẫn hiện được phần còn lại. */
    const load = useCallback(async () => {
        setLoading(true);
        setLoadError(null);

        const [statusResult, folderResult, readyResult] = await Promise.allSettled([
            getDocumentsStatus(),
            getFolderInfo(),
            getReady(),
        ]);

        if (statusResult.status === 'fulfilled') setStatus(statusResult.value);
        if (folderResult.status === 'fulfilled') setFolder(folderResult.value);
        if (readyResult.status === 'fulfilled') setReady(readyResult.value);

        // Ưu tiên báo lỗi `/documents/status` (quan trọng nhất), rồi tới `/ready`
        const firstFailure = statusResult.status === 'rejected'
            ? statusResult.reason
            : (readyResult.status === 'rejected' ? readyResult.reason : null);
        if (firstFailure) setLoadError(describeApiError(firstFailure));

        setLoading(false);
    }, []);

    useEffect(() => {
        if (!open) return;
        void load();
    }, [open, load]);

    // Esc + focus trap + aria-modal: Radix `Sheet` (Dialog) lo, không cần effect thủ công (KB-4.8)

    /** Đồng bộ = index tăng dần (KB-5.1). Không phá huỷ ⇒ không cần confirm như Refresh cũ. */
    const handleSync = async () => {
        setBusy('sync');
        setActionError(null);
        setSyncResult(null);
        setCleared(false);
        try {
            const result = await syncDocuments();
            setSyncResult(result);
            await load();
        } catch (error) {
            setActionError(describeApiError(error));
        } finally {
            setBusy(null);
        }
    };

    const handleConfirmClear = async () => {
        setBusy('clear');
        setActionError(null);
        setSyncResult(null);
        setCleared(false);
        try {
            await clearDocuments();
            setCleared(true);
            setPending(null);
            setClearInput('');
            await load();
        } catch (error) {
            setActionError(describeApiError(error));
        } finally {
            setBusy(null);
        }
    };

    return (
        <Sheet open={open} onOpenChange={(next) => {
            if (!next) onClose();
        }}>
            <SheetContent side="right" showCloseButton={false} className="w-full gap-0 p-0 sm:max-w-md">
                <SheetTitle className="sr-only">Kho tài liệu và trạng thái backend</SheetTitle>
                <DocumentsPanelContent
                    status={status}
                    folder={folder}
                    ready={ready}
                    loading={loading}
                    loadError={loadError}
                    actionError={actionError}
                    busy={busy}
                    pending={pending}
                    syncResult={syncResult}
                    cleared={cleared}
                    clearInput={clearInput}
                    onReload={() => void load()}
                    onClose={onClose}
                onSync={() => void handleSync()}
                onAskClear={() => {
                    setActionError(null);
                    setSyncResult(null);
                    setCleared(false);
                    setClearInput('');
                    setPending('clear');
                }}
                onCancel={() => {
                    setPending(null);
                    setClearInput('');
                }}
                onConfirmClear={() => void handleConfirmClear()}
                onClearInputChange={setClearInput}
                />
            </SheetContent>
        </Sheet>
    );
}

