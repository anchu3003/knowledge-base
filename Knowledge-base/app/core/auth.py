"""Auth tối giản bằng 1 token tĩnh (KB-5.5) — **mặc định TẮT**.

Bối cảnh: repo này là knowledge base cá nhân. Chạy `localhost` trong WSL thì không ai vào được, nhưng khi mở
LAN/VPS thì bất kỳ ai gõ `http://<ip>:8010` đều đọc được kho tài liệu, **lịch sử hội thoại** (`GET /conversations`)
và gọi được các endpoint phá huỷ (`DELETE /documents/clear`, `POST /documents/refresh`) — xem bảng so sánh trong
`Backlog.md`.

Thiết kế (Q&A KB-5.5 đã chốt):
- **1 token tĩnh** đọc từ env `API_TOKEN`, client gửi header `X-API-Key` ⇒ không kéo theo hệ user/role (YAGNI).
- So sánh **constant-time** (`secrets.compare_digest`) để không rò token qua timing.
- **Fail-closed**: bật auth mà `API_TOKEN` rỗng ⇒ **chặn tất cả** (không được coi "chưa cấu hình = cho qua").
- **Cờ `AUTH_ENABLED=false` mặc định**: code nằm sẵn, hành vi hiện tại không đổi; khi cần chỉ đặt
  `AUTH_ENABLED=true` + `API_TOKEN=...` là bật (không phải sửa code, không phải deploy lại FE).
- Endpoint công khai: `/health` (healthcheck Docker, KB-3.4) và `/` (root health). `/ready` **được bảo vệ**
  vì nó lộ cấu hình provider + số chunk.
- Response lỗi giữ đúng contract KB-3.1: `{"error": {code, message, request_id}}` + header `X-Request-ID`.

Viết dạng **pure ASGI** như `RequestIDMiddleware` để không bọc `StreamingResponse` của `/chat/stream`
(tránh ảnh hưởng disconnect/heartbeat ở KB-3.3).
"""

from __future__ import annotations

import logging
import secrets
from typing import Callable, Iterable

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import Settings, get_settings
from app.core.errors import error_body
from app.core.middleware import REQUEST_ID_HEADER, REQUEST_ID_STATE_KEY

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"
UNAUTHORIZED_CODE = "unauthorized"
UNAUTHORIZED_MESSAGE = "Missing or invalid API key."

#: Endpoint không cần token: `/health` cho healthcheck Docker (KB-3.4) và `/` (root health).
PUBLIC_PATHS: frozenset[str] = frozenset({"/", "/health"})


def is_public_path(path: str) -> bool:
    """`True` nếu path được phép gọi khi bật auth."""
    return path in PUBLIC_PATHS


def token_matches(provided: str | None, expected: str | None) -> bool:
    """So sánh token **constant-time**; token cấu hình rỗng ⇒ luôn `False` (fail-closed)."""
    if not expected:
        return False
    candidate = provided or ""
    return secrets.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


class ApiKeyMiddleware:
    """Chặn request không có `X-API-Key` hợp lệ khi `AUTH_ENABLED=true`."""

    def __init__(
            self,
            app: ASGIApp,
            settings_provider: Callable[[], Settings] = get_settings,
            public_paths: Iterable[str] = PUBLIC_PATHS,
    ) -> None:
        self.app = app
        self._settings_provider = settings_provider
        self._public_paths = frozenset(public_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = self._settings_provider()
        if not getattr(settings, "auth_enabled", False):
            # Cờ tắt (mặc định) ⇒ không tốn gì, hành vi y như trước KB-5.5.
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self._public_paths:
            await self.app(scope, receive, send)
            return

        provided = Headers(scope=scope).get(API_KEY_HEADER)
        expected = getattr(settings, "api_token", "") or ""
        if token_matches(provided, expected):
            await self.app(scope, receive, send)
            return

        request_id = (scope.get("state") or {}).get(REQUEST_ID_STATE_KEY) or "-"
        # Log không chứa token (rule 30-pii-safety): chỉ method + path + lý do.
        logger.warning(
            "auth rejected: request_id=%s method=%s path=%s reason=%s",
            request_id,
            scope.get("method", "-"),
            path,
            "no_token_configured" if not expected else "bad_or_missing_token",
        )

        response = JSONResponse(
            status_code=401,
            content=error_body(UNAUTHORIZED_CODE, UNAUTHORIZED_MESSAGE, request_id),
            headers={REQUEST_ID_HEADER: request_id},
        )
        await response(scope, receive, send)

