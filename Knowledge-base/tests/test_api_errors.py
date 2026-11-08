"""Test error contract ở tầng HTTP cho mọi endpoint (KB-3.5, bảo vệ KB-3.1).

Mọi assertion đều kiểm thêm "không lộ chi tiết nội bộ" — đây chính là thứ TD-4 để lọt trước đây.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.main import app

PROVIDER_URL = "https://api.groq.com/openai/v1"
LEAK_MARKERS = ("api.groq.com", "Traceback", "/home/", "RuntimeError", "gsk_")

PROVIDER_ERROR_CASES = [
    (ProviderAuthError(f"AuthenticationError: bad key {PROVIDER_URL}"), 502, "provider_auth_failed"),
    (ProviderRateLimitError(f"RateLimitError: 429 {PROVIDER_URL}"), 429, "provider_rate_limited"),
    (ProviderUnavailableError(f"APIConnectionError: dns {PROVIDER_URL}"), 503, "provider_unavailable"),
    (ProviderTimeoutError(f"APITimeoutError: no reply {PROVIDER_URL}"), 504, "provider_timeout"),
]


def assert_no_internal_leak(response):
    for marker in LEAK_MARKERS:
        assert marker not in response.text, f"lộ chi tiết nội bộ: {marker}"


# ------------------------------
# POST /chat — mapping lỗi provider (KB-3.1)
# ------------------------------
@pytest.mark.parametrize(
    "error,status,code",
    PROVIDER_ERROR_CASES,
    ids=["auth_502", "rate_limit_429", "unavailable_503", "timeout_504"],
)
def test_chat_maps_provider_errors(api_client, fake_chat_service, error, status, code):
    fake_chat_service.error = error

    response = api_client.post("/chat", json={"message": "xin chao"})
    body = response.json()

    assert response.status_code == status
    assert body["error"]["code"] == code
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    assert_no_internal_leak(response)


def test_unhandled_exception_returns_internal_error(api_client, fake_chat_service):
    fake_chat_service.error = RuntimeError(f"boom {PROVIDER_URL} /home/anchu/secret.yaml")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/chat", json={"message": "xin chao"})
    body = response.json()

    assert response.status_code == 500
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "Internal server error."
    assert_no_internal_leak(response)


# ------------------------------
# 422 + request-id
# ------------------------------
def test_validation_error_when_message_missing(api_client):
    response = api_client.post("/chat", json={})
    body = response.json()

    assert response.status_code == 422
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    locations = [detail["loc"] for detail in body["error"]["details"]]
    assert any("message" in loc for loc in locations)


def test_validation_error_does_not_echo_client_input(api_client):
    response = api_client.post("/chat", json={"temperature": "very-hot-value"})

    assert response.status_code == 422
    assert "very-hot-value" not in response.text


def test_client_request_id_is_echoed(api_client):
    response = api_client.post(
        "/chat", json={"message": "xin chao"}, headers={"X-Request-ID": "kb-3.5-trace-1"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "kb-3.5-trace-1"


# ------------------------------
# Routing + document endpoints
# ------------------------------
def test_unknown_route_returns_404_envelope(api_client):
    response = api_client.get("/khong-ton-tai")
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "not_found"
    assert "detail" not in body


def test_wrong_method_returns_405_envelope(api_client):
    response = api_client.get("/chat")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


@pytest.mark.parametrize(
    "method,path",
    [("get", "/documents/status"), ("post", "/documents/refresh"), ("delete", "/documents/clear")],
)
def test_documents_errors_map_to_document_store_error(api_client, fake_document_service, method, path):
    fake_document_service.error = RuntimeError(f"chroma failed /home/anchu/chroma_db {PROVIDER_URL}")

    response = getattr(api_client, method)(path)
    body = response.json()

    assert response.status_code == 500
    assert body["error"]["code"] == "document_store_error"
    assert_no_internal_leak(response)


def test_service_unavailable_when_services_not_initialized():
    # Không override dependency + không chạy lifespan ⇒ service toàn cục vẫn None
    response = TestClient(app).post("/chat", json={"message": "xin chao"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
