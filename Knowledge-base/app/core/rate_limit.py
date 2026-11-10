"""Rate limit phía server (TD-20) — **mặc định TẮT** (`RATE_LIMIT_ENABLED=false`).

Vì sao cần: mỗi câu `/chat` tốn 1 lần rerank CPU (~3–4 s) + 1 request provider (Groq free tier có TPM).
Ai vào được `http://<ip>:8010` (mở LAN/VPS — cùng bối cảnh KB-5.5 auth) đều có thể bấm liên tục làm
CPU/provider nghẽn, hoặc fuzz endpoint.

Thiết kế (1 người dùng, KHÔNG thêm Redis — AGENTS.md §3.4):

- **Sliding window** theo key = IP client (`scope["client"][0]`), giữ `deque` timestamp trong window.
  Chính xác hơn fixed-window (không có "burst gấp đôi" ở ranh giới window).
- **Chỉ áp cho đường tốn kém**: `/chat` + `/chat/stream` (`DEFAULT_PROTECTED_PATHS`). `/health`,
  `/ready`, `/conversations` không bị chặn (đọc rẻ, healthcheck phải qua được).
- **Fail-open khi cờ tắt**: chưa bật ⇒ middleware trả qua ngay, không tốn gì (hành vi như trước TD-20).
- Response 429 dùng **cùng envelope lỗi** KB-3.1 + header `Retry-After` (giây, làm tròn lên).
- Viết dạng **pure ASGI** (như `ApiKeyMiddleware`) để không bọc `StreamingResponse` của SSE — chạm
  wrapper là dễ hỏng disconnect/heartbeat của KB-3.3.

Giới hạn đã biết (ghi ở TD-17/TD-28): state **in-process** ⇒ nhiều uvicorn worker thì mỗi worker đếm
riêng (mức phạt thực tế = `limit × số worker`). Muốn chặt hơn phải có store dùng chung.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Iterable, Tuple

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import Settings, get_settings
from app.core.errors import error_body
from app.core.middleware import REQUEST_ID_HEADER, REQUEST_ID_STATE_KEY

logger = logging.getLogger(__name__)

#: Endpoint tốn kém cần chặn (TD-20). Mọi thứ khác đi qua tự do.
DEFAULT_PROTECTED_PATHS: frozenset[str] = frozenset({"/chat", "/chat/stream"})

RATE_LIMITED_CODE = "rate_limited"
RATE_LIMITED_MESSAGE = "Too many requests. Please retry later."

#: Chặn phình bộ nhớ khi bị quét từ nhiều IP: quá ngần này key ⇒ dọn key đã hết window.
MAX_TRACKED_KEYS = 10_000


class SlidingWindowLimiter:
    """Đếm request theo key trong `window_seconds`; thread-safe (ASGI + executor cùng chạm)."""

    def __init__(
            self,
            max_requests: int,
            window_seconds: float,
            clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(0.001, float(window_seconds))
        self._clock = clock
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self.blocked = 0

    def check(self, key: str) -> Tuple[bool, float]:
        """Trả `(allowed, retry_after_seconds)`. `retry_after = 0` khi được phép."""
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.max_requests:
                # Cửa sổ trượt: chỉ được gọi lại khi hit cũ nhất rời window.
                retry_after = max(0.0, hits[0] + self.window_seconds - now)
                self.blocked += 1
                return False, retry_after

            hits.append(now)
            self._maybe_prune(now)
            return True, 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self.blocked = 0

    def _maybe_prune(self, now: float) -> None:
        """Chỉ dọn khi bảng key phình to (không quét toàn bộ mỗi request)."""
        if len(self._hits) <= MAX_TRACKED_KEYS:
            return
        cutoff = now - self.window_seconds
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in stale:
            self._hits.pop(key, None)


def client_key(scope: Scope) -> str:
    """IP của client; thiếu (test/ASGI nội bộ) ⇒ `"unknown"`.

    **Không** đọc `X-Forwarded-For` (client tự đặt được ⇒ vô hiệu hoá rate limit). Đặt sau reverse proxy
    thật thì bật `uvicorn --proxy-headers` để `scope["client"]` là IP thật.
    """
    client = scope.get("client")
    if not client:
        return "unknown"
    try:
        return str(client[0] or "unknown")
    except (TypeError, IndexError):
        return "unknown"


def retry_after_seconds(value: float) -> int:
    """`Retry-After` (header HTTP) tính bằng **giây nguyên**, tối thiểu 1."""
    return max(1, int(math.ceil(value))) if value > 0 else 1


def current_settings() -> Settings:
    """Provider settings **mặc định** của middleware.

    Tách thành hàm (thay vì dùng thẳng `get_settings`) vì middleware được dựng lúc import app: default
    argument bind sẵn tham chiếu, nên test muốn bật/tắt cờ chỉ cần monkeypatch hàm này.
    """
    return get_settings()


class RateLimitMiddleware:
    """Chặn `protected_paths` vượt `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` mỗi IP."""

    def __init__(
            self,
            app: ASGIApp,
            settings_provider: Callable[[], Settings] | None = None,
            protected_paths: Iterable[str] = DEFAULT_PROTECTED_PATHS,
            limiter: SlidingWindowLimiter | None = None,
    ) -> None:

        self.app = app
        self._settings_provider = settings_provider
        self._protected_paths = frozenset(protected_paths)
        self._limiter = limiter
        self._limiter_signature: Tuple[int, float] | None = None
        self._lock = threading.Lock()

    def settings(self) -> Settings:
        """Settings hiện tại — resolve **lúc gọi**, không bind default arg lúc import app."""
        provider = self._settings_provider or current_settings
        return provider()



    # -- limiter sống theo settings hiện tại ---------------------------------
    @property
    def limiter(self) -> SlidingWindowLimiter | None:
        return self._limiter

    def _get_limiter(self, settings: Settings) -> SlidingWindowLimiter:
        if self._limiter is not None and self._limiter_signature is None:
            return self._limiter
        signature = (
            int(getattr(settings, "rate_limit_max_requests", 30)),
            float(getattr(settings, "rate_limit_window_seconds", 60.0)),
        )
        with self._lock:
            if self._limiter is None or signature != self._limiter_signature:
                # Đổi env (restart hoặc test override) ⇒ limiter mới, không dùng nhầm ngưỡng cũ.
                self._limiter = SlidingWindowLimiter(*signature)
                self._limiter_signature = signature
            return self._limiter

    def stats(self) -> Dict[str, object]:
        """Số liệu cho `/ready` — **không** lộ key/IP."""
        limiter = self._limiter
        if limiter is None:
            return {"enabled": False, "max_requests": 0, "window_seconds": 0.0, "blocked": 0}
        return {
            "enabled": True,
            "max_requests": limiter.max_requests,
            "window_seconds": limiter.window_seconds,
            "blocked": limiter.blocked,
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = self.settings()
        if not getattr(settings, "rate_limit_enabled", False):
            # Cờ tắt (mặc định) ⇒ không tốn gì, hành vi y như trước TD-20.
            await self.app(scope, receive, send)
            return

        if scope.get("path", "") not in self._protected_paths:
            await self.app(scope, receive, send)
            return

        allowed, retry_after = self._get_limiter(settings).check(client_key(scope))
        if allowed:
            await self.app(scope, receive, send)
            return

        request_id = (scope.get("state") or {}).get(REQUEST_ID_STATE_KEY) or "-"
        retry_seconds = retry_after_seconds(retry_after)
        # Log không chứa IP/token (rule 30-pii-safety): chỉ path + thời gian chờ.
        logger.warning(
            "rate limited: request_id=%s path=%s retry_after=%ss",
            request_id,
            scope.get("path", "-"),
            retry_seconds,
        )

        response = JSONResponse(
            status_code=429,
            content=error_body(RATE_LIMITED_CODE, RATE_LIMITED_MESSAGE, request_id),
            headers={REQUEST_ID_HEADER: request_id, "Retry-After": str(retry_seconds)},
        )
        await response(scope, receive, send)
