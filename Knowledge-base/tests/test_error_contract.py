"""Test error contract (KB-3.1): taxonomy + global handler + `X-Request-ID`.

Không cần LLM/Chroma/network:

- **unit**: exception của OpenAI SDK → `AppError` (`map_provider_error`);
- **service**: `ChatService` với fake LLM client raise từng loại lỗi;
- **HTTP**: `TestClient` + `dependency_overrides` — **không** dùng context manager nên lifespan
  không chạy (không load model, không mở ChromaDB).
"""
import asyncio
import logging
import re
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from app.core.errors import (
    AppError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    map_provider_error,
)
from app.main import app, get_chat_service
from app.models.schemas import ErrorResponse
from app.core.provider_retry import ProviderThrottle
from app.services.chat_service import ChatService
from app.services.pii_service import PIIRedactor

PROVIDER_URL = "https://api.groq.com/openai/v1/chat/completions"
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _request() -> httpx.Request:
    return httpx.Request("POST", PROVIDER_URL)


def _status_error(cls, status_code: int):
    return cls("provider refused the request", response=httpx.Response(status_code, request=_request()), body=None)


# ------------------------------
# 1. Taxonomy: SDK exception → AppError
# ------------------------------
SDK_ERROR_CASES = [
    ("timeout", APITimeoutError(request=_request()), ProviderTimeoutError, 504, "provider_timeout"),
    ("rate_limit", _status_error(RateLimitError, 429), ProviderRateLimitError, 429, "provider_rate_limited"),
    ("auth", _status_error(AuthenticationError, 401), ProviderAuthError, 502, "provider_auth_failed"),
    ("connection", APIConnectionError(request=_request()), ProviderUnavailableError, 503, "provider_unavailable"),
    ("api_error", APIError("upstream 500", request=_request(), body=None),
     ProviderUnavailableError, 503, "provider_unavailable"),
    ("builtin_connection", ConnectionError("dns down"), ProviderUnavailableError, 503, "provider_unavailable"),
    ("unknown", ValueError("something unexpected"), AppError, 500, "internal_error"),
]


@pytest.mark.parametrize(
    "exc,expected_cls,status,code",
    [case[1:] for case in SDK_ERROR_CASES],
    ids=[case[0] for case in SDK_ERROR_CASES],
)
def test_map_provider_error(exc, expected_cls, status, code):
    mapped = map_provider_error(exc)

    assert isinstance(mapped, expected_cls)
    assert mapped.code == code
    assert mapped.http_status == status
    # chi tiết nội bộ nằm ở `internal_detail` (chỉ để log), KHÔNG ở message public
    assert mapped.internal_detail and type(exc).__name__ in mapped.internal_detail
    assert "api.groq.com" not in mapped.public_message


# ------------------------------
# 2. ChatService: fake LLM client raise từng loại lỗi
# ------------------------------
class FakeDocumentService:
    async def search_similar_documents(self, query, k=3):
        return []

    def filter_by_relevance(self, docs, threshold=None):
        """KB-9.4: fake không lọc (test ngưỡng ở tests/test_relevance_filter.py)."""
        return list(docs), 0


class FailingLLM:
    """Fake LLM client: `agenerate`/`astream` đều raise lỗi provider."""

    temperature = 0.0
    max_tokens = 128

    def __init__(self, error):
        self.error = error

    async def agenerate(self, messages):
        raise self.error

    async def astream(self, messages):
        raise self.error
        yield  # pragma: no cover - giữ signature async generator


def make_chat_service(error) -> ChatService:
    """ChatService với fake LLM/document service (KB-5.9/TD-27: dùng builder chung).

    `provider_max_retries=0` để test này chỉ kiểm *mapping* lỗi (hành vi retry có file riêng: KB-3.2).
    """
    from tests.builders import make_chat_service as build_chat_service, make_settings

    settings = make_settings(provider_max_retries=0)
    service = build_chat_service(llm=FailingLLM(error), settings=settings)
    service.document_service = FakeDocumentService()
    return service



@pytest.mark.parametrize(
    "exc,expected_cls,status,code",
    [case[1:] for case in SDK_ERROR_CASES[:-1]],
    ids=[case[0] for case in SDK_ERROR_CASES[:-1]],
)
def test_chat_raises_mapped_app_error(exc, expected_cls, status, code):
    service = make_chat_service(exc)

    with pytest.raises(expected_cls) as excinfo:
        asyncio.run(service.chat(message="hello"))

    error = excinfo.value
    assert error.code == code
    assert error.http_status == status
    assert PROVIDER_URL not in error.public_message


def test_stream_chat_yields_normalised_error_event():
    service = make_chat_service(_status_error(RateLimitError, 429))

    async def collect():
        return [event async for event in service.stream_chat(message="hello", request_id="req-1")]

    events = asyncio.run(collect())
    error_events = [event for event in events if event.get("type") == "error"]

    assert len(error_events) == 1
    payload = error_events[0]["error"]  # KB-3.3: cùng schema envelope của /chat
    assert payload["code"] == "provider_rate_limited"
    assert payload["request_id"] == "req-1"
    assert PROVIDER_URL not in payload["message"]
    assert "RateLimitError" not in payload["message"]


# ------------------------------
# 3. HTTP layer: envelope lỗi + request-id
# ------------------------------
class FakeChatService:
    """Chat service giả cho tầng HTTP: raise lỗi cấu hình sẵn, hoặc trả answer tĩnh."""

    def __init__(self, error=None):
        self.error = error

    async def chat(self, **kwargs):
        if self.error is not None:
            raise self.error
        return {"answer": "ok", "conversation_id": "conv-1", "sources": [], "metadata": {}}


@pytest.fixture(autouse=True)
def _reset_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def make_client(*, chat_error=None, raise_server_exceptions=True) -> TestClient:
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(chat_error)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_root_endpoint_still_healthy_and_has_request_id():
    response = make_client().get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert uuid.UUID(response.headers["X-Request-ID"])  # uuid4 sinh ra khi client không gửi


def test_client_request_id_is_echoed_in_header_and_body():
    response = make_client(chat_error=ProviderRateLimitError("RateLimitError: 429 from api.groq.com")).post(
        "/chat", json={"message": "xin chao"}, headers={"X-Request-ID": "kb-3-1-trace-001"},
    )

    assert response.status_code == 429
    assert response.headers["X-Request-ID"] == "kb-3-1-trace-001"
    assert response.json()["error"]["request_id"] == "kb-3-1-trace-001"


def test_unsafe_client_request_id_is_replaced():
    response = make_client().get("/", headers={"X-Request-ID": "bad id with spaces"})

    request_id = response.headers["X-Request-ID"]
    assert request_id != "bad id with spaces"
    assert SAFE_REQUEST_ID.match(request_id)


@pytest.mark.parametrize(
    "error,status,code",
    [
        (ProviderAuthError("AuthenticationError: bad key for api.groq.com"), 502, "provider_auth_failed"),
        (ProviderRateLimitError("RateLimitError: 429 api.groq.com"), 429, "provider_rate_limited"),
        (ProviderUnavailableError("APIConnectionError: dns api.groq.com"), 503, "provider_unavailable"),
        (ProviderTimeoutError("APITimeoutError: no response from api.groq.com"), 504, "provider_timeout"),
    ],
    ids=["auth_502", "rate_limit_429", "connection_503", "timeout_504"],
)
def test_provider_errors_map_to_http_status(error, status, code):
    response = make_client(chat_error=error).post("/chat", json={"message": "xin chao"})
    body = response.json()

    assert response.status_code == status
    assert body["error"]["code"] == code
    assert body["error"]["message"] == error.public_message
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    ErrorResponse(**body)  # body khớp schema công bố

    # AC: không response lỗi nào lộ chi tiết nội bộ
    assert "api.groq.com" not in response.text
    assert "Traceback" not in response.text
    assert "RateLimitError" not in response.text


def test_unhandled_exception_returns_internal_error_without_leaking():
    client = make_client(
        chat_error=RuntimeError(f"boom {PROVIDER_URL} /home/anchu/secret/config.yaml"),
        raise_server_exceptions=False,
    )

    response = client.post("/chat", json={"message": "xin chao"})
    body = response.json()

    assert response.status_code == 500
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "Internal server error."
    for leaked in ("api.groq.com", "Traceback", "/home/anchu", "RuntimeError"):
        assert leaked not in response.text


def test_validation_error_uses_same_envelope_without_echoing_input():
    response = make_client().post("/chat", json={"temperature": "very-hot-value"})
    body = response.json()

    assert response.status_code == 422
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    assert body["error"]["details"]  # có loc/msg để client biết field nào sai
    assert any("message" in detail["loc"] for detail in body["error"]["details"])
    assert "very-hot-value" not in response.text  # không echo input của client
    ErrorResponse(**body)


def test_unknown_route_returns_404_envelope():
    response = make_client().get("/does-not-exist")
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "detail" not in body  # không còn format lỗi cũ của FastAPI


def test_wrong_method_returns_405_envelope():
    response = make_client().get("/chat")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_service_not_initialised_returns_503_envelope():
    # Không override dependency và không chạy lifespan ⇒ service vẫn None
    response = TestClient(app).post("/chat", json={"message": "xin chao"})
    body = response.json()

    assert response.status_code == 503
    assert body["error"]["code"] == "service_unavailable"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_request_id_is_logged(caplog):
    caplog.set_level(logging.INFO)

    make_client(chat_error=ProviderRateLimitError("RateLimitError: 429 api.groq.com")).post(
        "/chat", json={"message": "xin chao"}, headers={"X-Request-ID": "log-check-123"},
    )

    assert "request_id=log-check-123" in caplog.text
