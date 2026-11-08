"""SSE transport cho `POST /chat/stream` (KB-3.3).

Tách khỏi route để test được không cần HTTP:

- `SSE_HEADERS` — chống proxy buffer + tắt cache (`Cache-Control`, `Connection`, `X-Accel-Buffering`).
- `error_event(exc, request_id)` — event `error` **cùng schema** với envelope lỗi của `/chat`:
  `{"type": "error", "error": {"code", "message", "request_id"}}`.
- `sse_event_stream(...)` — bọc async iterator event của service thành chuỗi SSE:
  - mỗi event → `data: <json>\n\n`;
  - quá `heartbeat_seconds` không có event ⇒ gửi comment `: ping\n\n` (giữ kết nối qua proxy/idle timeout);
  - service raise ra ngoài ⇒ vẫn còn một `error` event (lưới an toàn) rồi đóng stream;
  - client disconnect ⇒ cancel task bơm event và **await** nó để generator của service nhận
    `CancelledError`/`GeneratorExit` và dọn dẹp (lưu partial answer — Q&A KB-3.3).

Vì sao dùng task + queue thay `asyncio.wait_for(anext(gen))`: `wait_for` **cancel** lần `__anext__`
đang chờ ⇒ giết luôn generator của service mỗi lần heartbeat. Task bơm riêng thì heartbeat không
đụng tới vòng lặp sinh token.
"""

import asyncio
import contextlib
import json
import logging
from typing import Any, AsyncIterator, Dict

from app.core.errors import AppError, map_provider_error

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
HEARTBEAT_COMMENT = ": ping\n\n"
_DONE = object()


def error_event(exc: BaseException, request_id: str = "-") -> Dict[str, Any]:
    """Event `error` chuẩn hoá — không chứa `str(exception)`/chi tiết nội bộ."""
    mapped = exc if isinstance(exc, AppError) else map_provider_error(exc)
    return {
        "type": "error",
        "error": {"code": mapped.code, "message": mapped.public_message, "request_id": request_id},
    }


def format_event(event: Dict[str, Any]) -> str:
    """Serialize một event thành frame SSE."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def sse_event_stream(
        events: AsyncIterator[Dict[str, Any]],
        *,
        request_id: str = "-",
        heartbeat_seconds: float = 15.0,
) -> AsyncIterator[str]:
    """Biến iterator event của service thành stream SSE có heartbeat + dọn dẹp khi disconnect."""
    queue: asyncio.Queue = asyncio.Queue()
    timeout = max(0.01, float(heartbeat_seconds))

    async def pump() -> None:
        try:
            async for event in events:
                await queue.put(event)
        except asyncio.CancelledError:
            raise  # disconnect: để generator của service tự xử lý ở `finally`/`except`
        except Exception as exc:  # lưới an toàn: service đã map lỗi, đây là lỗi ngoài dự kiến
            event = error_event(exc, request_id)
            logger.error("sse stream failed: code=%s request_id=%s", event["error"]["code"], request_id)
            await queue.put(event)
        finally:
            await queue.put(_DONE)

    task = asyncio.ensure_future(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                yield HEARTBEAT_COMMENT
                continue
            if item is _DONE:
                return
            yield format_event(item)
    finally:
        if not task.done():
            task.cancel()
        # Await để chắc chắn generator của service nhận cancel và chạy cleanup (lưu partial answer).
        with contextlib.suppress(asyncio.CancelledError):
            await task
