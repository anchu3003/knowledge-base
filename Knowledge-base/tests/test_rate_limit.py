"""Test rate limit per-IP (TD-20) — thuần ASGI, không chạm Chroma/LLM/network.

3 tầng:
1. `SlidingWindowLimiter` (logic cửa sổ trượt, `clock` giả ⇒ không `sleep`).
2. `RateLimitMiddleware` (cờ tắt/bật, path được bảo vệ, envelope lỗi + `Retry-After`).
3. Endpoint thật qua `TestClient`: bật cờ ⇒ request thứ 2 trả 429.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import (
    RATE_LIMITED_CODE,
    RateLimitMiddleware,
    SlidingWindowLimiter,
    client_key,
    retry_after_seconds,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# ------------------------------
# 1. SlidingWindowLimiter
# ------------------------------
def test_limiter_allows_up_to_max_requests():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60, clock=clock)
    assert [limiter.check("1.2.3.4")[0] for _ in range(3)] == [True, True, True]


def test_limiter_blocks_after_limit_and_reports_retry_after():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60, clock=clock)
    limiter.check("ip")
    clock.advance(10)
    limiter.check("ip")
    clock.advance(5)

    allowed, retry_after = limiter.check("ip")
    assert allowed is False
    # hit đầu ở t=1000 rời window ở 1060, hiện tại 1015 ⇒ còn 45 s
    assert retry_after == pytest.approx(45.0)
    assert limiter.blocked == 1


def test_limiter_slides_window_and_lets_request_through_again():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=30, clock=clock)
    assert limiter.check("ip")[0] is True
    assert limiter.check("ip")[0] is False
    clock.advance(30.001)
    assert limiter.check("ip")[0] is True


def test_limiter_is_per_key():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60, clock=clock)
    assert limiter.check("a")[0] is True
    assert limiter.check("a")[0] is False
    assert limiter.check("b")[0] is True  # IP khác không bị ảnh hưởng


def test_limiter_reset_clears_state():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60, clock=clock)
    limiter.check("ip")
    assert limiter.check("ip")[0] is False
    limiter.reset()
    assert limiter.check("ip")[0] is True
    assert limiter.blocked == 0


def test_client_key_handles_missing_client_and_bad_shape():
    assert client_key({"type": "http", "client": ("10.0.0.5", 1234)}) == "10.0.0.5"
    assert client_key({"type": "http"}) == "unknown"
    assert client_key({"type": "http", "client": None}) == "unknown"


def test_retry_after_seconds_rounds_up_with_floor_of_one():
    assert retry_after_seconds(0) == 1
    assert retry_after_seconds(0.2) == 1
    assert retry_after_seconds(1.1) == 2
    assert retry_after_seconds(42.0) == 42


# ------------------------------
# 2. Middleware (pure ASGI)
# ------------------------------
class RecordingApp:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, scope, receive, send):
        self.calls += 1
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def _scope(path="/chat", client=("10.0.0.5", 1234), state=None):
    scope = {
        "type": "http",
        "path": path,
        "method": "POST",
        "headers": [],
        "client": client,
    }
    if state is not None:
        scope["state"] = state
    return scope


async def _collect(app, scope):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return sent


def _settings(**overrides):
    values = dict(rate_limit_enabled=True, rate_limit_max_requests=2, rate_limit_window_seconds=60.0)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_middleware_passes_through_when_flag_disabled():
    inner = RecordingApp()
    mw = RateLimitMiddleware(inner, settings_provider=lambda: _settings(rate_limit_enabled=False))

    async def run():
        for _ in range(5):
            await _collect(mw, _scope())

    asyncio.run(run())
    assert inner.calls == 5


def test_middleware_ignores_unprotected_path():
    inner = RecordingApp()
    mw = RateLimitMiddleware(inner, settings_provider=lambda: _settings(rate_limit_max_requests=1))

    async def run():
        for _ in range(3):
            await _collect(mw, _scope(path="/health"))
            await _collect(mw, _scope(path="/conversations"))
            await _collect(mw, _scope(path="/ready"))

    asyncio.run(run())
    assert inner.calls == 9


def test_middleware_returns_429_with_retry_after_and_request_id():
    inner = RecordingApp()
    mw = RateLimitMiddleware(inner, settings_provider=lambda: _settings(rate_limit_max_requests=1))

    async def run():
        await _collect(mw, _scope(state={"request_id": "req-123"}))
        return await _collect(mw, _scope(state={"request_id": "req-123"}))

    sent = asyncio.run(run())
    assert inner.calls == 1
    start = sent[0]
    assert start["status"] == 429
    headers = {k.decode(): v.decode() for k, v in start["headers"]}
    assert headers["retry-after"] == "60"
    assert headers["x-request-id"] == "req-123"

    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    payload = json.loads(body)
    assert payload["error"]["code"] == RATE_LIMITED_CODE
    assert payload["error"]["request_id"] == "req-123"


def test_middleware_limits_per_ip():
    inner = RecordingApp()
    mw = RateLimitMiddleware(inner, settings_provider=lambda: _settings(rate_limit_max_requests=1))

    async def run():
        await _collect(mw, _scope(client=("10.0.0.5", 1)))
        await _collect(mw, _scope(client=("10.0.0.5", 2)))  # bị chặn
        await _collect(mw, _scope(client=("10.0.0.6", 3)))  # IP khác ⇒ qua

    asyncio.run(run())
    assert inner.calls == 2


# ------------------------------
# 3. Endpoint thật (TestClient)
# ------------------------------
def test_chat_endpoint_returns_429_when_rate_limit_enabled(monkeypatch, api_client):
    """Bật cờ + limiter 1 request ⇒ câu thứ 2 bị 429 (kèm `Retry-After`, `X-Request-ID`)."""
    import app.main as main_module
    import app.core.rate_limit as rate_limit_module

    _enable_rate_limit(monkeypatch, main_module)

    first = api_client.post("/chat", json={"message": "Kafka là gì?"})
    second = api_client.post("/chat", json={"message": "Kafka là gì?"})

    assert first.status_code == 200, first.text
    assert second.status_code == 429
    assert second.json()["error"]["code"] == RATE_LIMITED_CODE
    assert second.headers["Retry-After"] == "60"
    assert second.headers["X-Request-ID"]


def test_health_and_conversations_not_rate_limited(monkeypatch, api_client):
    """Endpoint rẻ (`/health`, `/conversations`) phải qua được dù limiter đã cạn."""
    import app.main as main_module

    _enable_rate_limit(monkeypatch, main_module)

    api_client.post("/chat", json={"message": "một"})
    assert api_client.post("/chat", json={"message": "hai"}).status_code == 429
    assert api_client.get("/health").status_code == 200
    assert api_client.get("/conversations").status_code == 200


def _enable_rate_limit(monkeypatch, main_module) -> None:
    """Bật cờ qua provider + siết limiter **dùng chung** (middleware đã giữ tham chiếu từ lúc import)."""
    import app.core.rate_limit as rate_limit_module

    settings = main_module._rate_limit_settings
    monkeypatch.setattr(
        rate_limit_module,
        "current_settings",
        lambda: SimpleNamespace(**{**vars(settings), "rate_limit_enabled": True}),
    )
    limiter = main_module._rate_limiter
    limiter.reset()
    monkeypatch.setattr(limiter, "max_requests", 1)
    monkeypatch.setattr(limiter, "window_seconds", 60.0)


