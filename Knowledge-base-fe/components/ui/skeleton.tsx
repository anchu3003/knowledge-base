import {cn} from '@/lib/utils';

/**
 * Skeleton (KB-4.8) — placeholder khi đang chờ (KB-4.11 sẽ dùng cho pha "đang truy hồi").
 * `aria-hidden` để screen reader không đọc nội dung giả.
 */
function Skeleton({className, ...props}: React.ComponentProps<'div'>) {
    return (
        <div
            data-slot="skeleton"
            aria-hidden="true"
            className={cn('bg-muted animate-pulse rounded-md', className)}
            {...props}
        />
    );
}

export {Skeleton};
