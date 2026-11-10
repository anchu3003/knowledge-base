/**
 * Map `error.code` của backend → message tiếng Việt cho người dùng (KB-4.1).
 *
 * Q&A KB-4.1 đã chốt: **tự viết message tiếng Việt theo `code`** (không hiện nguyên `error.message` tiếng Anh
 * của BE), và `retryable` quyết định có hiện nút "Thử lại" hay không.
 */

import { API_BASE_URL, ApiError, NETWORK_ERROR_CODE } from './api';

export interface ApiErrorView {
    /** Mã lỗi (hằng số từ BE, hoặc `network_error` do FE sinh). */
    code: string;
    /** Câu hiển thị chính cho người dùng. */
    message: string;
    /** Gợi ý hành động ngắn (có thể rỗng). */
    hint: string;
    /** `request_id` để đối chiếu log BE (không có → `-`). */
    requestId: string;
    /** Có nên hiện nút "Thử lại" không. */
    retryable: boolean;
}

interface CodeView {
    message: string;
    hint?: string;
    retryable: boolean;
}

const CODE_VIEWS: Record<string, CodeView> = {
    network_error: {
        message: 'Không kết nối được tới server.',
        // KB-4.7: dùng đúng URL đã build (compose chạy BE ở 8010, dev ở 8000) thay vì hardcode
        hint: `Kiểm tra backend đang chạy (${API_BASE_URL}) rồi thử lại.`,
        retryable: true,
    },
    request_timeout: {
        message: 'Backend xử lý quá lâu nên FE đã ngừng chờ.',
        hint: 'Re-index toàn bộ tài liệu có thể mất vài chục phút — xem log backend rồi kiểm tra lại trạng thái index.',
        retryable: false,
    },
    provider_rate_limited: {
        message: 'Đã chạm hạn mức của provider (Groq free tier).',
        hint: 'Chờ khoảng 30 giây rồi thử lại — quota theo phút.',
        retryable: true,
    },
    provider_unavailable: {
        message: 'Provider LLM đang không phản hồi.',
        hint: 'Thử lại sau ít giây; nếu lặp lại, kiểm tra kết nối mạng của máy chủ.',
        retryable: true,
    },
    provider_timeout: {
        message: 'Provider LLM phản hồi quá lâu nên đã bị huỷ.',
        hint: 'Thử lại; câu hỏi ngắn hơn thường nhanh hơn.',
        retryable: true,
    },
    provider_auth_failed: {
        message: 'Backend chưa cấu hình đúng API key của provider.',
        hint: 'Kiểm tra OPENAI_API_KEY / OPENAI_BASE_URL trong .env của backend.',
        retryable: false,
    },
    unauthorized: {
        message: 'Cần API token để truy cập kho tài liệu này.',
        hint: 'Nhập token trong ô phía trên (lấy từ `API_TOKEN` của backend).',
        retryable: false,
    },
    service_unavailable: {
        message: 'Backend chưa sẵn sàng (service chưa khởi tạo xong).',
        hint: 'Chờ vài giây rồi thử lại.',
        retryable: true,
    },
    document_store_error: {
        message: 'Backend gặp lỗi khi đọc/ghi kho tài liệu.',
        hint: 'Thử lại; nếu vẫn lỗi, xem log backend theo request_id bên dưới.',
        retryable: false,
    },
    documents_folder_empty: {
        message: 'Folder tài liệu không tồn tại hoặc không có file hỗ trợ.',
        hint: 'Refresh đã bị chặn để không xoá index hiện tại. Kiểm tra DOCUMENTS_FOLDER của backend (trong Docker: mount ./Interview).',
        retryable: false,
    },
    validation_error: {
        message: 'Yêu cầu chưa hợp lệ.',
        hint: 'Kiểm tra lại nội dung câu hỏi và các tham số (max tokens, temperature).',
        retryable: false,
    },
    not_found: {
        message: 'Không tìm thấy endpoint trên backend.',
        hint: 'Kiểm tra NEXT_PUBLIC_API_PROXY_URL có trỏ đúng backend không.',
        retryable: false,
    },
    method_not_allowed: {
        message: 'Backend không hỗ trợ thao tác này.',
        hint: 'Đây là lỗi cấu hình phía FE — báo lại khi gặp.',
        retryable: false,
    },
    internal_error: {
        message: 'Backend gặp lỗi không xác định.',
        hint: 'Gửi request_id bên dưới để tra log backend.',
        retryable: false,
    },
};

/** Các code coi là "thử lại được" kể cả khi BE đổi code mới (fallback theo HTTP status). */
const RETRYABLE_STATUS = new Set([429, 502, 503, 504]);

export function describeApiError(error: unknown): ApiErrorView {
    if (error instanceof ApiError) {
        const view = CODE_VIEWS[error.code];
        if (view) {
            return {
                code: error.code,
                message: view.message,
                hint: view.hint ?? '',
                requestId: error.requestId,
                retryable: view.retryable,
            };
        }
        // Code lạ (BE thêm code mới) → vẫn hiển thị được, dựa vào HTTP status để đoán retryable
        return {
            code: error.code,
            message: 'Yêu cầu thất bại.',
            hint: error.status ? `HTTP ${error.status}.` : '',
            requestId: error.requestId,
            retryable: RETRYABLE_STATUS.has(error.status),
        };
    }

    return {
        code: 'internal_error',
        message: 'Có lỗi không xác định ở phía trình duyệt.',
        hint: '',
        requestId: '-',
        retryable: false,
    };
}

export { NETWORK_ERROR_CODE };
