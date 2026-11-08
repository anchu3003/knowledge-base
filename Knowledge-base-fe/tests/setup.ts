/**
 * Setup dùng chung cho vitest (KB-4.6).
 *
 * jsdom **không** có `scrollIntoView`/`clipboard` (component dùng cả hai) ⇒ stub ở đây thay vì sửa component.
 */

import '@testing-library/jest-dom/vitest';
import {afterEach, vi} from 'vitest';
import {cleanup} from '@testing-library/react';

// jsdom thiếu API layout — component gọi khi bấm chip citation (KB-4.3)
if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn();
}

// `navigator.clipboard` chỉ có trong secure context; jsdom không implement
if (!navigator.clipboard) {
    Object.defineProperty(navigator, 'clipboard', {
        value: {writeText: vi.fn().mockResolvedValue(undefined)},
        configurable: true,
    });
}

afterEach(() => {
    cleanup();
});
