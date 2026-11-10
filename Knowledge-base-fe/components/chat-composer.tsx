'use client';

import {useState} from 'react';
import {ArrowUp, ChevronDown, Settings2, Square} from 'lucide-react';

import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Label} from '@/components/ui/label';
import {Slider} from '@/components/ui/slider';

interface ChatComposerProps {
    value: string;
    onChange: (value: string) => void;
    onSend: () => void;
    /** Có khi đang stream (KB-4.4) — nút chuyển thành Stop */
    onStop?: () => void;
    isLoading: boolean;
    /** `NEXT_PUBLIC_STREAMING` — false thì không có Stop (request blocking) */
    streamingEnabled: boolean;
    formError?: string | null;
    /** `null` = theo server (không gửi field ⇒ BE dùng env) — KB-9.2. */
    maxTokens: number | null;
    onMaxTokensChange: (value: number | null) => void;
    temperature: number | null;
    onTemperatureChange: (value: number | null) => void;
    /** Trả cả 2 về "theo server". */
    onUseServerDefaults: () => void;
    /** Cả 2 đang là `null`. */
    usingServerDefaults: boolean;
    maxTokensLimit: {min: number; max: number};
    /** Model BE đang dùng — hiển thị read-only (BE chưa nhận model từ client; KB-4.9 sẽ bỏ hẳn select giả) */
    model?: string;
}

/**
 * Composer (KB-4.8) — sticky ở đáy, `max-w-3xl` canh giữa, thay khối input lệch của bản onboarding.
 *
 * Tham số thật sự gửi được cho BE: `max_tokens`, `temperature` (`ChatRequest`). `model` chỉ **hiển thị**
 * vì BE luôn dùng `OPENAI_MODEL` từ env.
 */
export function ChatComposer({
                                 value,
                                 onChange,
                                 onSend,
                                 onStop,
                                 isLoading,
                                 streamingEnabled,
                                 formError,
                                 maxTokens,
                                 onMaxTokensChange,
                                 temperature,
                                 onTemperatureChange,
                                 onUseServerDefaults,
                                 usingServerDefaults,
                                 maxTokensLimit,
                                 model,
                             }: ChatComposerProps) {
    const [showAdvanced, setShowAdvanced] = useState(false);
    const canSend = value.trim().length > 0 && !isLoading;

    return (
        <div className="sticky bottom-0 bg-background/95 backdrop-blur">
            {/*
              Canh mép (KB-4.9): cột chat là `max-w-3xl` + `px-3`, trong mỗi hàng message có avatar
              (2.25rem) + gap (0.625rem) ⇒ bubble bị thụt vào 2.875rem mỗi bên.
              Composer thêm đúng khoảng đó (`sm:`) để cạnh trái thẳng mép bubble AI và cạnh phải thẳng
              mép bubble "Bạn" — dưới `sm` avatar bị ẩn nên không thêm.
            */}
            <div className="mx-auto w-full max-w-3xl px-3 py-2.5 sm:px-[calc(0.75rem_+_2.875rem)]">
                {formError && (
                    <p role="alert" className="mb-2 text-sm text-destructive">
                        {formError}
                    </p>
                )}

                <div data-testid="composer-row" className="flex items-end gap-2">
                    <textarea
                        value={value}
                        onChange={(event) => onChange(event.target.value)}
                        onKeyDown={(event) => {
                            // Enter = gửi, Shift+Enter = xuống dòng
                            if (event.key === 'Enter' && !event.shiftKey) {
                                event.preventDefault();
                                if (canSend) onSend();
                            }
                        }}
                        rows={1}
                        placeholder="Hỏi gì đó về tài liệu của bạn… (Enter để gửi, Shift+Enter để xuống dòng)"
                        aria-label="Câu hỏi"
                        className="max-h-40 min-h-9 flex-1 resize-none rounded-lg border border-border bg-card px-3 py-1.5 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                    />
                    {isLoading && streamingEnabled && onStop ? (
                        <Button
                            onClick={onStop}
                            size="icon"
                            variant="destructive"
                            aria-label="Dừng trả lời"
                            className="rounded-lg"
                        >
                            <Square className="size-3.5" fill="currentColor"/>
                        </Button>
                    ) : (
                        <Button
                            onClick={onSend}
                            disabled={!canSend}
                            size="icon"
                            aria-label="Gửi câu hỏi"
                            className="rounded-lg"
                        >
                            <ArrowUp className="size-4"/>
                        </Button>
                    )}
                </div>

                <div className="mt-1.5 flex items-center justify-between gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowAdvanced((open) => !open)}
                        aria-expanded={showAdvanced}
                        className="gap-1.5 text-muted-foreground"
                    >
                        <Settings2 className="size-3.5"/>
                        Tuỳ chọn
                        <ChevronDown className={`size-3.5 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}/>
                    </Button>
                    {model && <span className="truncate font-mono text-[11px] text-muted-foreground">{model}</span>}
                </div>

                {showAdvanced && (
                    <div className="mt-2 grid grid-cols-1 gap-3 rounded-xl bg-muted/40 p-3 sm:grid-cols-2">
                        <div className="flex flex-col gap-1.5">
                            <div className="flex items-center justify-between gap-2">
                                <Label htmlFor="max-tokens" className="text-xs text-muted-foreground">
                                    Max tokens
                                </Label>
                                {usingServerDefaults && (
                                    <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                                        theo server
                                    </span>
                                )}
                            </div>
                            <Input
                                id="max-tokens"
                                type="number"
                                min={maxTokensLimit.min}
                                max={maxTokensLimit.max}
                                placeholder={`auto (server)`}
                                value={maxTokens ?? ''}
                                onChange={(event) => {
                                    const raw = event.target.value.trim();
                                    // rỗng ⇒ quay về "theo server" (gửi undefined, BE dùng env)
                                    onMaxTokensChange(raw === '' ? null : Number(raw));
                                }}
                                className="h-8"
                            />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label htmlFor="temperature" className="text-xs text-muted-foreground">
                                Temperature: {temperature === null ? 'auto (server)' : temperature.toFixed(2)}
                            </Label>
                            <Slider
                                id="temperature"
                                min={0}
                                max={1}
                                step={0.01}
                                value={[temperature ?? 0.2]}
                                onValueChange={([next]) => onTemperatureChange(next)}
                                aria-label="Temperature"
                                className="py-1.5"
                            />
                        </div>
                        <div className="sm:col-span-2 flex items-center justify-between gap-2">
                            <p className="text-[11px] text-muted-foreground">
                                Để trống = dùng default của server (env <span className="font-mono">DEFAULT_*</span>).
                                Thay đổi được lưu cho lần sau.
                            </p>
                            <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-[11px]"
                                    onClick={onUseServerDefaults} disabled={usingServerDefaults}>
                                Dùng theo server
                            </Button>
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
}
