'use client';

/**
 * Cấu hình **chỉnh lúc chạy** (KB-9.4) — đọc `GET /settings`, sửa rồi `PUT /settings`.
 *
 * Vì sao cần: tham số retrieval/rerank trước đây chỉ đổi được bằng `.env` + restart ⇒ không ai thử. BE mở
 * whitelist (`tunables`) kèm `min`/`max` + `defaults` ⇒ UI **dựng control từ dữ liệu**, không hard-code
 * danh sách: thêm tham số ở BE là UI tự có.
 */

import {useEffect, useState} from 'react';
import {RotateCcw, Settings2} from 'lucide-react';

import {getSettings, resetSettings, updateSettings} from '@/lib/api';
import {describeApiError, type ApiErrorView} from '@/lib/errors';
import type {RuntimeSetting, SettingsResponse} from '@/lib/types';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Label} from '@/components/ui/label';

interface SettingsPanelProps {
    /** Lỗi khi lưu — báo qua banner của panel cha (1 chỗ hiện lỗi). */
    onError?: (view: ApiErrorView | null) => void;
}

/** Nhãn ngắn tiếng Việt; `description` của BE làm tooltip. */
const LABELS: Record<string, string> = {
    relevance_min_score: 'Ngưỡng liên quan (bỏ nguồn dưới ngưỡng)',
    retrieval_k: 'Số chunk đưa vào prompt',
    rerank_top_n: 'Số ứng viên rerank',
    hybrid_alpha: 'Trọng số dense ↔ BM25',
    hybrid_candidate_k: 'Ứng viên trước rerank',
    multi_query_enabled: 'Tách câu nhiều ý',
    multi_query_max_parts: 'Số phần tối đa',
    dedup_enabled: 'Gộp chunk trùng',
    max_chunks_per_file: 'Tối đa chunk / file',
    enable_rerank: 'Bật rerank',
    default_temperature: 'Temperature mặc định',
    default_max_tokens: 'max_tokens mặc định',
};

export function SettingsPanel({onError}: SettingsPanelProps) {
    const [data, setData] = useState<SettingsResponse | null>(null);
    const [draft, setDraft] = useState<Record<string, number | boolean>>({});
    const [busy, setBusy] = useState(false);
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const response = await getSettings();
                if (cancelled) return;
                setData(response);
                setDraft(response.values);
            } catch (error) {
                if (!cancelled) onError?.(describeApiError(error));
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [onError]);

    if (!data) return null;

    const changed = Object.entries(draft)
        .filter(([key, value]) => data.values[key] !== value)
        .map(([key]) => key);

    const save = async () => {
        setBusy(true);
        setSaved(false);
        onError?.(null);
        try {
            const payload = Object.fromEntries(changed.map((key) => [key, draft[key]]));
            const response = await updateSettings(payload);
            setData({...data, values: response.values, overridden: response.overridden});
            setDraft(response.values);
            setSaved(true);
        } catch (error) {
            onError?.(describeApiError(error));
        } finally {
            setBusy(false);
        }
    };

    const reset = async () => {
        setBusy(true);
        onError?.(null);
        try {
            const response = await resetSettings();
            setData({...data, values: response.values, overridden: []});
            setDraft(response.values);
            setSaved(false);
        } catch (error) {
            onError?.(describeApiError(error));
        } finally {
            setBusy(false);
        }
    };

    const renderControl = (tunable: RuntimeSetting) => {
        const value = draft[tunable.key];
        if (tunable.kind === 'bool') {
            return (
                <input
                    type="checkbox"
                    id={`setting-${tunable.key}`}
                    className="h-4 w-4"
                    checked={Boolean(value)}
                    onChange={(event) => setDraft({...draft, [tunable.key]: event.target.checked})}
                />
            );
        }
        return (
            <Input
                id={`setting-${tunable.key}`}
                type="number"
                className="h-8 w-20 shrink-0 text-right"
                min={tunable.min ?? undefined}
                max={tunable.max ?? undefined}
                step={tunable.kind === 'float' ? 0.01 : 1}
                value={Number(value)}
                onChange={(event) => setDraft({...draft, [tunable.key]: Number(event.target.value)})}
            />
        );
    };

    return (
        <section className="space-y-2" data-testid="settings-panel">
            <div className="flex items-center justify-between gap-2">
                <h3 className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    <Settings2 className="h-3.5 w-3.5"/> Cấu hình server
                </h3>
                <span className="text-[11px] text-slate-500 dark:text-slate-400" data-testid="settings-state">
                    {data.overridden.length > 0 ? `${data.overridden.length} tham số đã đổi` : 'đang dùng mặc định'}
                </span>
            </div>

            <div className="max-h-60 space-y-1.5 overflow-y-auto pr-1">
                {data.tunables.map((tunable) => (
                    <div key={tunable.key} className="flex min-w-0 items-center justify-between gap-2">
                        <Label htmlFor={`setting-${tunable.key}`}
                               className="min-w-0 flex-1 truncate text-xs font-normal text-slate-600 dark:text-slate-300"
                               title={tunable.description}>
                            {LABELS[tunable.key] ?? tunable.key}
                            {data.overridden.includes(tunable.key) && (
                                <span className="ml-1 rounded bg-amber-100 px-1 text-[10px] text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                                    đã đổi
                                </span>
                            )}
                        </Label>
                        {renderControl(tunable)}
                    </div>
                ))}
            </div>

            <div className="flex items-center justify-end gap-2 pt-1">
                {saved && <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400">Đã lưu</span>}
                <Button size="sm" variant="ghost" className="h-7 gap-1 px-2 text-[11px]"
                        onClick={() => void reset()} disabled={busy}>
                    <RotateCcw className="h-3 w-3"/> Mặc định
                </Button>
                <Button size="sm" className="h-7 px-2 text-[11px]"
                        onClick={() => void save()} disabled={busy || changed.length === 0}>
                    Lưu {changed.length > 0 ? `(${changed.length})` : ''}
                </Button>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Áp dụng ngay, không cần restart. Tham số cần re-index (chunk size, embedding model) không đổi ở đây.
            </p>
        </section>
    );
}
