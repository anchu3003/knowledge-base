"""Retry + timeout + concurrency cho call tới LLM provider (KB-3.2).

Vì sao không để SDK tự retry:

- `ChatOpenAI`/`AzureChatOpenAI` được tạo với `max_retries=0` — **service là nơi duy nhất** quyết định
  retry (tránh 2 tầng retry chồng nhau, backoff mù, không tôn trọng `Retry-After`);
- ngân sách retry lấy từ env (`PROVIDER_MAX_RETRIES`, `PROVIDER_RETRY_BASE_DELAY`), backoff có **jitter**;
- **mọi** call provider đi qua `ProviderThrottle` để concurrency không vượt `PROVIDER_MAX_CONCURRENCY`
  (Groq free tier TPM 8000 — 2 call đồng thời là vượt hạn mức, đo thật ở KB-2.3).

Chỉ retry khi **có khả năng thành công**: `429`, `5xx`, timeout, lỗi kết nối. `4xx` khác (auth, request sai,
prompt quá dài) retry chỉ tốn quota ⇒ fail ngay.
"""

import asyncio
import logging
import random
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from app.core.errors import AppError, map_provider_error

logger = logging.getLogger(__name__)

# Log **không** chứa prompt/context — chỉ op + attempt + loại lỗi + delay.
_RETRY_LOG = "provider retry op=%s attempt=%s/%s error=%s delay=%.2fs"


def is_retryable(exc: BaseException) -> bool:
    """`429` / `5xx` / timeout / lỗi kết nối thì retry; còn lại fail ngay."""
    if isinstance(exc, AppError):
        return False
    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, RateLimitError):  # 429 (cũng là `APIStatusError`)
        return True
    if isinstance(exc, APIStatusError):
        return int(getattr(exc, "status_code", 0) or 0) >= 500
    return False


def parse_retry_after(raw: Any) -> Optional[float]:
    """Parse header `Retry-After` → giây.

    Groq có lúc trả **mili-giây** (vd `2500`) ⇒ giá trị ≥ 100 coi là ms. Không parse được (HTTP-date…)
    → `None` (dùng backoff thường).
    """
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value / 1000.0 if value >= 100 else value


def retry_after_seconds(exc: BaseException) -> Optional[float]:
    """Đọc `Retry-After` từ response của exception (nếu provider có gửi)."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if not headers:
        return None
    try:
        return parse_retry_after(headers.get("retry-after"))
    except Exception:  # pragma: no cover - headers lạ
        return None


def compute_delay(
        attempt: int,
        base_delay: float,
        retry_after: Optional[float] = None,
        max_delay: Optional[float] = None,
) -> float:
    """Delay trước lần retry thứ `attempt` (0-based).

    - có `Retry-After` ⇒ dùng đúng giá trị provider, cap ở `max_delay`;
    - không có ⇒ exponential backoff + **equal jitter**: `raw = base * 2**attempt`,
      delay ∈ [`raw/2`, `raw`] ⇒ nhiều client không retry cùng một thời điểm.
    """
    if max_delay is None or max_delay <= 0:
        max_delay = 60.0
    if retry_after is not None:
        return min(max(retry_after, 0.0), max_delay)
    raw = min(base_delay * (2 ** attempt), max_delay)
    return raw / 2 + random.uniform(0, raw / 2)


def to_app_error(exc: BaseException, *, op: str, attempts: int) -> AppError:
    """Đổi lỗi cuối cùng sang taxonomy KB-3.1, kèm số attempt vào `internal_detail` (chỉ để log)."""
    if isinstance(exc, AppError):
        return exc
    mapped = map_provider_error(exc)
    mapped.internal_detail = f"{mapped.internal_detail} (op={op}, attempts={attempts})"
    return mapped


class ProviderThrottle:
    """Cổng duy nhất gọi provider: giới hạn concurrency + retry/backoff có ngân sách."""

    def __init__(self, settings: Any, *, sleep: Optional[Callable[[float], Awaitable[None]]] = None) -> None:
        self.settings = settings
        self.max_retries = max(0, int(getattr(settings, "provider_max_retries", 2) or 0))
        self.base_delay = float(getattr(settings, "provider_retry_base_delay", 2.0) or 0.0)
        self.max_delay = float(getattr(settings, "provider_timeout_seconds", 60.0) or 60.0)
        self._max_concurrency = max(1, int(getattr(settings, "provider_max_concurrency", 1) or 1))
        self._semaphore = asyncio.Semaphore(self._max_concurrency)
        # Cho test inject sleep (mặc định `asyncio.sleep`) — không cần monkeypatch toàn cục.
        self._sleep = sleep or asyncio.sleep

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    async def run(self, call: Callable[[], Awaitable[Any]], *, op: str, retry: bool = True) -> Any:
        """Chạy `call()` trong giới hạn concurrency; retry theo ngân sách (nếu `retry=True`)."""
        async with self._semaphore:
            budget = self.max_retries if retry else 0
            attempt = 0
            while True:
                try:
                    return await call()
                except Exception as exc:
                    if not is_retryable(exc) or attempt >= budget:
                        raise to_app_error(exc, op=op, attempts=attempt + 1) from exc
                    delay = compute_delay(attempt, self.base_delay, retry_after_seconds(exc), self.max_delay)
                    logger.warning(_RETRY_LOG, op, attempt + 1, budget, type(exc).__name__, delay)
                    await self._sleep(delay)
                    attempt += 1

    async def stream(self, make_stream: Callable[[], AsyncIterator[Any]], *, op: str) -> AsyncIterator[Any]:
        """Yield chunk từ provider; retry **chỉ khi chưa có token nào** (retry giữa stream là vô nghĩa).

        Semaphore giữ suốt thời gian stream vì request vẫn đang chiếm quota của provider.
        """
        async with self._semaphore:
            attempt = 0
            while True:
                started = False
                try:
                    async for chunk in make_stream():
                        started = True
                        yield chunk
                    return
                except Exception as exc:
                    if started or not is_retryable(exc) or attempt >= self.max_retries:
                        raise to_app_error(exc, op=op, attempts=attempt + 1) from exc
                    delay = compute_delay(attempt, self.base_delay, retry_after_seconds(exc), self.max_delay)
                    logger.warning(_RETRY_LOG, op, attempt + 1, self.max_retries, type(exc).__name__, delay)
                    await self._sleep(delay)
                    attempt += 1
