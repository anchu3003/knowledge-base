"""Middleware `X-Request-ID` (KB-3.1).

Mỗi request có một `request_id`:

- dùng header `X-Request-ID` của client **nếu hợp lệ** (chỉ `[A-Za-z0-9._-]`, ≤ 64 ký tự —
  chặn header/log injection), không thì sinh `uuid4`;
- lưu vào `request.state.request_id` để handler/endpoint đọc được;
- trả lại trong response header `X-Request-ID` (kể cả response lỗi, để client đối chiếu `error.request_id`);
- log một dòng/request (INFO) — log lỗi do handler ghi kèm `request_id`.

Viết dạng **pure ASGI** (không dùng `BaseHTTPMiddleware`) để không bọc `StreamingResponse`
của `/chat/stream` trong task group phụ — tránh ảnh hưởng disconnect/heartbeat ở KB-3.3.
"""

import logging
import re
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_STATE_KEY = "request_id"

# Chỉ nhận id "sạch" từ client (chặn newline/space trong log + header dài bất thường).
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

logger = logging.getLogger(__name__)


def get_request_id(request: Request) -> str:
    """Đọc `request_id` từ `request.state` (fallback `"-"` khi middleware bị bỏ qua)."""
    return getattr(request.state, REQUEST_ID_STATE_KEY, None) or "-"


class RequestIDMiddleware:
    """Gán/sinh `request_id` cho mỗi request HTTP và trả lại trong header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound = (Headers(scope=scope).get(REQUEST_ID_HEADER) or "").strip()
        request_id = inbound if _SAFE_REQUEST_ID.match(inbound) else str(uuid.uuid4())

        scope.setdefault("state", {})[REQUEST_ID_STATE_KEY] = request_id

        status_code = 0

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "request_id=%s method=%s path=%s status=%s",
                request_id,
                scope.get("method", "-"),
                scope.get("path", "-"),
                status_code or "-",
            )
