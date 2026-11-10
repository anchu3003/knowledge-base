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
    maxTokens: number;
    onMaxTokensChange: (value: number) => void;
    temperature: number;
    onTemperatureChange: (value: number) => void;
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
                            <Label htmlFor="max-tokens" className="text-xs text-muted-foreground">
                                Max tokens
                            </Label>
                            <Input
                                id="max-tokens"
                                type="number"
                                min={1}
                                max={2000}
                                value={maxTokens}
                                onChange={(event) => onMaxTokensChange(Number(event.target.value))}
                                className="h-8"
                            />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label htmlFor="temperature" className="text-xs text-muted-foreground">
                                Temperature: {temperature.toFixed(2)}
                            </Label>
                            <Slider
                                id="temperature"
                                min={0}
                                max={1}
                                step={0.01}
                                value={[temperature]}
                                onValueChange={([next]) => onTemperatureChange(next)}
                                aria-label="Temperature"
                                className="py-1.5"
                            />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
