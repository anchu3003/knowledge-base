"""Error taxonomy dùng chung cho API (KB-3.1).

Một **nguồn sự thật duy nhất** về lỗi:

- service raise `AppError` (hoặc subclass) — **không** raise `HTTPException`;
- exception handler ở `app/main.py` serialize thành
  `{"error": {"code": "<code>", "message": "<message>", "request_id": "<id>"}}`.

Quy ước:

| Field | Ý nghĩa |
|---|---|
| `code` | snake_case, **hằng số** trên class → client switch theo code, không parse message |
| `http_status` | HTTP status trả về |
| `public_message` | message **chung**, không chứa chi tiết nội bộ (host provider, path, traceback, `str(e)`) |
| `internal_detail` | `str(exception)` gốc — **chỉ dùng để log**, không bao giờ ra response |

Q&A KB-3.1: (Q1) đổi contract lỗi sang `{"error": {...}}`; (Q2) message **chung, không hint**
hành động (không nói "kiểm tra OPENAI_API_KEY") — hint chi tiết nằm ở log.
"""

from typing import Dict, Optional, Tuple

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)


class AppError(Exception):
    """Base error: code ổn định + HTTP status + message an toàn cho client."""

    code: str = "internal_error"
    http_status: int = 500
    public_message: str = "Internal server error."

    def __init__(
            self,
            internal_detail: Optional[str] = None,
            *,
            code: Optional[str] = None,
            http_status: Optional[int] = None,
            message: Optional[str] = None,
    ) -> None:
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        if message is not None:
            self.public_message = message
        self.internal_detail = internal_detail
        super().__init__(self.public_message)

    def __str__(self) -> str:  # chỉ dùng cho log/debug
        detail = f" ({self.internal_detail})" if self.internal_detail else ""
        return f"{self.code} [{self.http_status}]: {self.public_message}{detail}"


# ------------------------------
# Provider (LLM) errors
# ------------------------------
class ProviderAuthError(AppError):
    """Provider từ chối credential của mình (sai key/hết hạn) → 502."""

    code = "provider_auth_failed"
    http_status = 502
    public_message = "The language model provider rejected our credentials."


class ProviderRateLimitError(AppError):
    """Provider báo hết quota/rate limit (Groq free tier TPM) → 429."""

    code = "provider_rate_limited"
    http_status = 429
    public_message = "The language model provider rate limit was reached. Please retry later."


class ProviderUnavailableError(AppError):
    """Không gọi được provider (mạng/hạ tầng/5xx của provider) → 503."""

    code = "provider_unavailable"
    http_status = 503
    public_message = "The language model provider is currently unavailable."


class ProviderTimeoutError(AppError):
    """Provider không trả lời trong thời gian cho phép → 504."""

    code = "provider_timeout"
    http_status = 504
    public_message = "The language model provider did not respond in time."


# ------------------------------
# Document store / resource errors
# ------------------------------
class DocumentStoreError(AppError):
    """Lỗi khi thao tác trên vector store / tài liệu → 500."""

    code = "document_store_error"
    http_status = 500
    public_message = "The document store operation failed."


class DocumentsFolderEmptyError(AppError):
    """Folder tài liệu không tồn tại hoặc không có file hỗ trợ → 409.

    KB-4.10: `POST /documents/refresh` clear index rồi auto-load; nếu folder rỗng (vd `.dockerignore`
    loại folder khỏi image) thì sẽ **xoá sạch index mà không index lại được** ⇒ chặn trước khi clear.
    """

    code = "documents_folder_empty"
    http_status = 409
    public_message = "Documents folder is missing or has no supported files."


class NotFoundError(AppError):
    """Không tìm thấy tài nguyên → 404."""

    code = "not_found"
    http_status = 404
    public_message = "Resource not found."


class ServiceUnavailableError(AppError):
    """Service chưa được khởi tạo (dependency injection) → 503."""

    code = "service_unavailable"
    http_status = 503
    public_message = "Service is not available yet. Please retry shortly."

    def __str__(self) -> str:  # chỉ dùng cho log/debug
        detail = f" ({self.internal_detail})" if self.internal_detail else ""
        return f"{self.code} [{self.http_status}]: {self.public_message}{detail}"

# ------------------------------
# Mapping helpers
# ------------------------------
def map_provider_error(exc: BaseException) -> AppError:
    """Map exception của OpenAI-compatible SDK sang `AppError`.

    Thứ tự kiểm tra quan trọng: `APITimeoutError` ⊂ `APIConnectionError` ⊂ `APIError`, còn
    `RateLimitError`/`AuthenticationError` cũng là `APIError` con — nên check subclass trước.
    Exception lạ (không thuộc SDK) → `AppError` 500 `internal_error`.
    """
    detail = f"{type(exc).__name__}: {exc}"

    if isinstance(exc, APITimeoutError):
        return ProviderTimeoutError(detail)
    if isinstance(exc, RateLimitError):
        return ProviderRateLimitError(detail)
    if isinstance(exc, AuthenticationError):
        return ProviderAuthError(detail)
    if isinstance(exc, (APIConnectionError, ConnectionError)):
        return ProviderUnavailableError(detail)
    if isinstance(exc, APIError):
        return ProviderUnavailableError(detail)
    return AppError(detail)


# status → (code, message) cho lỗi do framework raise (404 route, 405, …)
_HTTP_STATUS_ERRORS: Dict[int, Tuple[str, str]] = {
    400: ("bad_request", "The request is invalid."),
    401: ("unauthorized", "Authentication is required."),
    403: ("forbidden", "Access to this resource is forbidden."),
    404: ("not_found", "Resource not found."),
    405: ("method_not_allowed", "Method not allowed for this endpoint."),
    413: ("payload_too_large", "The request payload is too large."),
    500: ("internal_error", "Internal server error."),
    503: ("service_unavailable", "Service is not available yet. Please retry shortly."),
}


def http_status_error(status_code: int, internal_detail: Optional[str] = None) -> AppError:
    """Đổi `HTTPException`/status của framework sang `AppError` cùng envelope."""
    code, message = _HTTP_STATUS_ERRORS.get(status_code, ("http_error", "Request failed."))
    return AppError(internal_detail, code=code, http_status=status_code, message=message)


def error_body(code: str, message: str, request_id: str) -> Dict[str, Dict[str, str]]:
    """Body lỗi duy nhất của API: `{"error": {code, message, request_id}}`."""
    return {"error": {"code": code, "message": message, "request_id": request_id}}
