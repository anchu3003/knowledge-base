'use client';

import {useEffect, useState} from 'react';
import {Loader2} from 'lucide-react';

import {Skeleton} from '@/components/ui/skeleton';
import {phaseLabelWithElapsed, type StreamPhase} from '@/lib/stream-phase';

interface StreamStatusProps {
    /** Chỉ hiện với 2 pha đang chạy. */
    phase: StreamPhase;
    /** `Date.now()` lúc bấm gửi (null ⇒ không chạy) */
    startedAt: number | null;
}

/**
 * Khối trạng thái khi đang chờ (KB-4.11) — thay spinner câm.
 *
 * Hiện nhãn pha + **số giây đã chờ**, cập nhật 500ms/lần. `startedAt` do `page.tsx` đặt khi gửi;
 * `phase` chuyển `retrieving → writing` khi nhận event `start` của BE.
 *
 * Vì sao đếm bằng `setInterval` trong effect (không `Date.now()` trong render): `react-hooks/purity`
 * coi `Date.now()` trong thân component là impure ⇒ state chỉ được set trong callback interval.
 */
export function StreamStatus({phase, startedAt}: StreamStatusProps) {
    const [now, setNow] = useState<number | null>(null);

    useEffect(() => {
        if (startedAt === null) return;
        const timer = setInterval(() => setNow(Date.now()), 500);
        return () => clearInterval(timer);
    }, [startedAt]);

    const elapsedMs = startedAt === null ? 0 : Math.max(0, (now ?? startedAt) - startedAt);
    const label = phaseLabelWithElapsed(phase, elapsedMs);

    if (!label) return null;

    return (
        <div className="flex items-start gap-2.5" role="status" aria-live="polite">
            <div
                className="mt-0.5 hidden size-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground sm:flex">
                AI
            </div>
            <div className="w-full max-w-[88%] space-y-2 rounded-2xl border border-border bg-card px-3.5 py-3">
                <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                    <Loader2 className="size-3.5 animate-spin"/>
                    <span data-testid="stream-phase">{label}</span>
                </div>
                {phase === 'retrieving' && (
                    <p className="text-[11px] text-muted-foreground">
                        Bước này chậm nhất (~8–13s) vì phải rerank trên CPU.
                    </p>
                )}
                <Skeleton className="h-3 w-1/3"/>
                <Skeleton className="h-3 w-5/6"/>
                <Skeleton className="h-3 w-2/3"/>
            </div>
        </div>
    );
}
