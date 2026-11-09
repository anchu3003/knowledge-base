"""Test provider resilience (KB-3.2): retry/backoff, `Retry-After`, timeout, concurrency.

Không cần LLM/network: fake callable raise **exception SDK thật** (`openai.*`) + inject `sleep`
(`ProviderThrottle(sleep=...)`) nên test chạy mili-giây, không phải chờ backoff thật.
"""
import asyncio
import logging
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

from app.core.config import Settings
from app.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.core.provider_retry import (
    ProviderThrottle,
    compute_delay,
    is_retryable,
    parse_retry_after,
    retry_after_seconds,
)
from app.main import app, get_chat_service
from app.services.chat_service import ChatService
from app.services.pii_service import PIIRedactor

PROVIDER_URL = "https://api.groq.com/openai/v1/chat/completions"


def _request() -> httpx.Request:
    return httpx.Request("POST", PROVIDER_URL)


def _sdk_error(cls, status_code=429, headers=None, message="provider said no"):
    response = httpx.Response(status_code, request=_request(), headers=headers or {})
    return cls(message, response=response, body=None)


class SleepRecorder:
    """Ghi lại delay thay vì ngủ thật."""

    def __init__(self):
        self.delays = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


class ScriptedCall:
    """Callable trả kết quả theo kịch bản: phần tử `Exception` thì raise, còn lại return."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    async def __call__(self):
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if isinstance(item, BaseException):
            raise item
        return item


def make_throttle(**overrides):
    values = dict(
        provider_max_retries=2,
        provider_retry_base_delay=2.0,
        provider_timeout_seconds=60.0,
        provider_max_concurrency=1,
    )
    values.update(overrides)
    recorder = SleepRecorder()
    return ProviderThrottle(SimpleNamespace(**values), sleep=recorder), recorder


# ------------------------------
# 1. Helper thuần: parse Retry-After + phân loại lỗi + delay
# ------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [("3", 3.0), ("2.5", 2.5), ("2500", 2.5), ("0", None), ("-1", None), ("abc", None), (None, None)],
)
def test_parse_retry_after_seconds_and_milliseconds(raw, expected):
    assert parse_retry_after(raw) == expected


def test_retry_after_is_read_from_response_headers():
    exc = _sdk_error(RateLimitError, headers={"retry-after": "4"})

    assert retry_after_seconds(exc) == 4.0
    assert retry_after_seconds(APITimeoutError(request=_request())) is None


@pytest.mark.parametrize(
    "exc,expected",
    [
        (_sdk_error(RateLimitError, 429), True),
        (_sdk_error(InternalServerError, 500), True),
        (_sdk_error(InternalServerError, 503), True),
        (APITimeoutError(request=_request()), True),
        (APIConnectionError(request=_request()), True),
        (_sdk_error(AuthenticationError, 401), False),
        (_sdk_error(BadRequestError, 400), False),
        (ValueError("nope"), False),
    ],
    ids=["429", "500", "503", "timeout", "connection", "401", "400", "value_error"],
)
def test_is_retryable_matrix(exc, expected):
    assert is_retryable(exc) is expected


def test_compute_delay_is_equal_jitter_within_exponential_bounds():
    for attempt, low, high in [(0, 1.0, 2.0), (1, 2.0, 4.0), (2, 4.0, 8.0)]:
        delay = compute_delay(attempt, base_delay=2.0, max_delay=60.0)
        assert low <= delay <= high


def test_compute_delay_prefers_retry_after_and_caps_it():
    assert compute_delay(0, base_delay=2.0, retry_after=1.5, max_delay=60.0) == 1.5
    assert compute_delay(0, base_delay=2.0, retry_after=999, max_delay=60.0) == 60.0
    assert compute_delay(9, base_delay=2.0, max_delay=8.0) <= 8.0


# ------------------------------
# 2. Retry budget + mapping lỗi (AC1–AC4)
# ------------------------------
def test_retry_then_success_calls_twice_and_waits_backoff():
    throttle, recorder = make_throttle()
    call = ScriptedCall([_sdk_error(RateLimitError, 429), "answer"])

    result = asyncio.run(throttle.run(call, op="chat"))

    assert result == "answer"
    assert call.calls == 2
    assert len(recorder.delays) == 1
    assert 1.0 <= recorder.delays[0] <= 2.0  # equal jitter quanh base 2.0


def test_exhausted_budget_raises_provider_rate_limit_error():
    throttle, recorder = make_throttle(provider_max_retries=2)
    call = ScriptedCall([_sdk_error(RateLimitError, 429)])

    with pytest.raises(ProviderRateLimitError) as excinfo:
        asyncio.run(throttle.run(call, op="chat"))

    error = excinfo.value
    assert error.code == "provider_rate_limited"
    assert error.http_status == 429
    assert "attempts=3" in error.internal_detail
    assert call.calls == 3  # 1 lần đầu + 2 retry
    assert len(recorder.delays) == 2
    assert 1.0 <= recorder.delays[0] <= 2.0
    assert 2.0 <= recorder.delays[1] <= 4.0


def test_timeout_maps_to_504_after_budget():
    throttle, _ = make_throttle(provider_max_retries=1)
    call = ScriptedCall([APITimeoutError(request=_request())])

    with pytest.raises(ProviderTimeoutError) as excinfo:
        asyncio.run(throttle.run(call, op="chat"))

    assert excinfo.value.http_status == 504
    assert excinfo.value.code == "provider_timeout"
    assert call.calls == 2


def test_server_error_is_retried():
    throttle, _ = make_throttle()
    call = ScriptedCall([_sdk_error(InternalServerError, 500), "answer"])

    assert asyncio.run(throttle.run(call, op="chat")) == "answer"
    assert call.calls == 2


@pytest.mark.parametrize(
    "exc,error_cls",
    [(_sdk_error(AuthenticationError, 401), ProviderAuthError), (_sdk_error(BadRequestError, 400), ProviderUnavailableError)],
    ids=["auth_401", "bad_request_400"],
)
def test_non_retryable_errors_fail_fast(exc, error_cls):
    throttle, recorder = make_throttle()
    call = ScriptedCall([exc])

    with pytest.raises(error_cls):
        asyncio.run(throttle.run(call, op="chat"))

    assert call.calls == 1  # AC: 4xx khác 429 KHÔNG retry
    assert recorder.delays == []


def test_retry_after_header_overrides_backoff():
    throttle, recorder = make_throttle()
    call = ScriptedCall([_sdk_error(RateLimitError, 429, headers={"retry-after": "1.25"}), "answer"])

    asyncio.run(throttle.run(call, op="chat"))

    assert recorder.delays == [1.25]


def test_retry_can_be_disabled_per_call():
    throttle, recorder = make_throttle()
    call = ScriptedCall([_sdk_error(RateLimitError, 429)])

    with pytest.raises(ProviderRateLimitError):
        asyncio.run(throttle.run(call, op="rewrite", retry=False))

    assert call.calls == 1
    assert recorder.delays == []


# ------------------------------
# 3. Concurrency (semaphore) — AC5
# ------------------------------
def _concurrency_probe(throttle, tasks=3):
    state = {"active": 0, "max_active": 0}

    async def call():
        state["active"] += 1
        state["max_active"] = max(state["max_active"], state["active"])
        await asyncio.sleep(0.01)
        state["active"] -= 1
        return "ok"

    async def run_all():
        return await asyncio.gather(*(throttle.run(call, op="chat") for _ in range(tasks)))

    assert asyncio.run(run_all()) == ["ok"] * tasks
    return state["max_active"]


def test_concurrency_one_serialises_provider_calls():
    throttle, _ = make_throttle(provider_max_concurrency=1, provider_max_retries=0)

    assert _concurrency_probe(throttle) == 1


def test_concurrency_two_allows_overlap():
    throttle, _ = make_throttle(provider_max_concurrency=2, provider_max_retries=0)

    assert _concurrency_probe(throttle) == 2


# ------------------------------
# 4. Stream: retry chỉ trước token đầu tiên
# ------------------------------
def test_stream_retries_before_first_token():
    throttle, recorder = make_throttle()
    attempts = {"count": 0}

    def make_stream():
        attempts["count"] += 1
        if attempts["count"] == 1:
            async def failing():
                raise _sdk_error(RateLimitError, 429)
                yield  # pragma: no cover
            return failing()

        async def ok():
            yield "a"
            yield "b"
        return ok()

    async def collect():
        return [chunk async for chunk in throttle.stream(make_stream, op="stream_chat")]

    assert asyncio.run(collect()) == ["a", "b"]
    assert attempts["count"] == 2
    assert len(recorder.delays) == 1


def test_stream_does_not_retry_after_first_token():
    throttle, recorder = make_throttle()
    attempts = {"count": 0}

    def make_stream():
        attempts["count"] += 1

        async def partial():
            yield "a"
            raise _sdk_error(RateLimitError, 429)
        return partial()

    async def collect():
        received = []
        with pytest.raises(ProviderRateLimitError):
            async for chunk in throttle.stream(make_stream, op="stream_chat"):
                received.append(chunk)
        return received

    assert asyncio.run(collect()) == ["a"]  # token đã gửi thì không retry nữa
    assert attempts["count"] == 1
    assert recorder.delays == []


# ------------------------------
# 5. Tích hợp ChatService: retry nằm ở service, rewrite thì không
# ------------------------------
class FakeDocumentService:
    async def search_similar_documents(self, query, k=3):
        return []


class CountingLLM:
    """Fake LLM: đếm số lần gọi provider và luôn raise lỗi cấu hình sẵn."""

    temperature = 0.0
    max_tokens = 128

    def __init__(self, error):
        self.error = error
        self.calls = 0

    async def agenerate(self, messages):
        self.calls += 1
        raise self.error

    async def astream(self, messages):
        self.calls += 1
        raise self.error
        yield  # pragma: no cover


def make_chat_service(llm, *, enable_query_rewrite=False, recorder=None, **provider_overrides):
    """KB-5.9 (TD-27): builder chung + throttle riêng (để đo retry)."""
    from tests.builders import make_chat_service as build_chat_service, make_settings

    settings = make_settings(
        enable_query_rewrite=enable_query_rewrite,
        provider_max_retries=provider_overrides.pop("provider_max_retries", 2),
        **provider_overrides,
    )
    service = build_chat_service(llm=llm, settings=settings)
    service.provider = ProviderThrottle(settings, sleep=recorder or SleepRecorder())
    return service


def test_chat_service_retries_until_budget_then_raises():
    recorder = SleepRecorder()
    llm = CountingLLM(_sdk_error(RateLimitError, 429))
    service = make_chat_service(llm, recorder=recorder, provider_max_retries=2)

    with pytest.raises(ProviderRateLimitError):
        asyncio.run(service.chat(message="xin chao"))

    assert llm.calls == 3  # 1 + 2 retry
    assert len(recorder.delays) == 2


def test_query_rewrite_is_not_retried():
    recorder = SleepRecorder()
    llm = CountingLLM(_sdk_error(RateLimitError, 429))
    service = make_chat_service(llm, enable_query_rewrite=True, recorder=recorder)

    with pytest.raises(ProviderRateLimitError):
        asyncio.run(service.chat(message="xin chao"))

    # 1 call rewrite (không retry) + 3 call chat (1 + 2 retry) = 4
    assert llm.calls == 4
    assert len(recorder.delays) == 2


def test_stream_chat_retries_then_reports_error_event():
    recorder = SleepRecorder()
    llm = CountingLLM(_sdk_error(RateLimitError, 429))
    service = make_chat_service(llm, recorder=recorder)

    async def collect():
        return [event async for event in service.stream_chat(message="xin chao")]

    events = asyncio.run(collect())
    error_events = [event for event in events if event.get("type") == "error"]

    assert llm.calls == 3
    assert len(error_events) == 1
    assert error_events[0]["error"]["code"] == "provider_rate_limited"  # schema lồng (KB-3.3)
    assert error_events[0]["error"]["request_id"] == "-"


def test_retry_logs_contain_no_prompt_or_context(caplog):
    caplog.set_level(logging.INFO)
    recorder = SleepRecorder()
    llm = CountingLLM(_sdk_error(RateLimitError, 429))
    service = make_chat_service(llm, recorder=recorder)

    with pytest.raises(ProviderRateLimitError):
        asyncio.run(service.chat(message="PROMPT_MARKER_SECRET"))

    assert "provider retry op=chat" in caplog.text
    assert "PROMPT_MARKER_SECRET" not in caplog.text  # AC: log không chứa prompt/context
    assert "No relevant documents found" not in caplog.text


# ------------------------------
# 6. Wiring: env → SDK/client → HTTP
# ------------------------------
PROVIDER_ENV_VARS = (
    "PROVIDER_TIMEOUT_SECONDS",
    "PROVIDER_MAX_RETRIES",
    "PROVIDER_RETRY_BASE_DELAY",
    "PROVIDER_MAX_CONCURRENCY",
)


def test_settings_provider_defaults(monkeypatch):
    for name in PROVIDER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost")

    settings = Settings()

    assert settings.provider_timeout_seconds == 60.0
    assert settings.provider_max_retries == 2
    assert settings.provider_retry_base_delay == 2.0
    assert settings.provider_max_concurrency == 1


def test_llm_client_gets_timeout_and_zero_sdk_retries(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost")
    monkeypatch.setenv("PROVIDER_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("PROVIDER_MAX_CONCURRENCY", "1")

    service = ChatService(Settings(), SimpleNamespace())

    assert service.llm.max_retries == 0  # SDK không retry: service là tầng retry duy nhất
    assert service.llm.request_timeout == 45.0
    assert service.provider.max_concurrency == 1


@pytest.mark.parametrize(
    "error,status,code",
    [
        (_sdk_error(RateLimitError, 429), 429, "provider_rate_limited"),
        (APITimeoutError(request=_request()), 504, "provider_timeout"),
    ],
    ids=["rate_limit_429", "timeout_504"],
)
def test_http_status_when_retry_budget_is_exhausted(error, status, code):
    recorder = SleepRecorder()
    llm = CountingLLM(error)
    service = make_chat_service(llm, recorder=recorder)

    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        response = TestClient(app).post("/chat", json={"message": "xin chao"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert llm.calls == 3  # AC: hết PROVIDER_MAX_RETRIES (2) mới trả lỗi
