'use client';

import * as React from 'react';
import * as SliderPrimitive from '@radix-ui/react-slider';

import {cn} from '@/lib/utils';

/**
 * Slider shadcn (KB-4.8) — dùng cho `temperature` trong composer.
 * Radix Slider có keyboard + aria sẵn (`role="slider"`), thay cho `<input type="range">` thô.
 */
function Slider({
                    className,
                    defaultValue,
                    value,
                    min = 0,
                    max = 100,
                    ...props
                }: React.ComponentProps<typeof SliderPrimitive.Root>) {
    // Số thumb = số giá trị (1 thumb với slider đơn)
    const thumbCount = Array.isArray(value) ? value.length : Array.isArray(defaultValue) ? defaultValue.length : 1;

    return (
        <SliderPrimitive.Root
            data-slot="slider"
            defaultValue={defaultValue}
            value={value}
            min={min}
            max={max}
            className={cn('relative flex w-full touch-none items-center select-none', className)}
            {...props}
        >
            <SliderPrimitive.Track className="bg-muted relative h-1.5 w-full grow overflow-hidden rounded-full">
                <SliderPrimitive.Range className="bg-primary absolute h-full"/>
            </SliderPrimitive.Track>
            {Array.from({length: thumbCount}).map((_, index) => (
                <SliderPrimitive.Thumb
                    key={index}
                    className="border-primary bg-background block size-4 rounded-full border-2 shadow-sm transition-[color,box-shadow] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
                />
            ))}
        </SliderPrimitive.Root>
    );
}

export {Slider};
