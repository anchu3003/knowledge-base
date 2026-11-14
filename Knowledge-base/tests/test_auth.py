"""Test auth token tĩnh (KB-5.5) — mặc định TẮT, bật thì fail-closed.

Dùng `TestClient` với `ApiKeyMiddleware` được cấu hình qua `settings_provider` giả ⇒ không phụ thuộc `.env`,
không chạy lifespan, không cần model/Chroma.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import API_KEY_HEADER, PUBLIC_PATHS, ApiKeyMiddleware, is_public_path, token_matches
from app.core.errors import UnauthorizedError

TOKEN = "token-test-123"


def make_app(*, auth_enabled: bool, api_token: str = TOKEN) -> FastAPI:
    """App nhỏ: 1 endpoint công khai (`/health`) + 1 endpoint bảo vệ (`/documents/status`)."""
    settings = SimpleNamespace(auth_enabled=auth_enabled, api_token=api_token)
    app = FastAPI()
    app.add_middleware(ApiKeyMiddleware, settings_provider=lambda: settings)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/documents/status")
    async def status():
        return {"document_count": 601}

    return app


# ------------------------------ helper thuần

def test_token_matches_is_constant_time_compatible():
    assert token_matches(TOKEN, TOKEN) is True
    assert token_matches("sai", TOKEN) is False
    assert token_matches(None, TOKEN) is False


def test_token_matches_fail_closed_when_not_configured():
    """Bật auth mà token rỗng ⇒ **không** được coi là "cho qua"."""
    assert token_matches("", "") is False
    assert token_matches("bất-kỳ", "") is False


def test_public_paths():
    assert is_public_path("/health") is True
    assert is_public_path("/") is True
    assert is_public_path("/ready") is False
    assert PUBLIC_PATHS == frozenset({"/", "/health"})


# ------------------------------ hành vi HTTP

def test_auth_disabled_lets_everything_through():
    """Mặc định `AUTH_ENABLED=false` ⇒ hành vi y như trước KB-5.5."""
    client = TestClient(make_app(auth_enabled=False, api_token=""))

    assert client.get("/documents/status").status_code == 200
    assert client.get("/health").status_code == 200


def test_auth_enabled_blocks_without_token():
    client = TestClient(make_app(auth_enabled=True))

    response = client.get("/documents/status")

    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "unauthorized"
    assert error["message"] == "Missing or invalid API key."
    assert error["request_id"]  # contract KB-3.1


def test_auth_enabled_blocks_wrong_token():
    client = TestClient(make_app(auth_enabled=True))

    response = client.get("/documents/status", headers={API_KEY_HEADER: "sai-token"})

    assert response.status_code == 401


def test_auth_enabled_allows_correct_token():
    client = TestClient(make_app(auth_enabled=True))

    response = client.get("/documents/status", headers={API_KEY_HEADER: TOKEN})

    assert response.status_code == 200
    assert response.json() == {"document_count": 601}


def test_health_is_public_even_when_auth_enabled():
    """Healthcheck Docker (KB-3.4) không được vỡ khi bật auth."""
    client = TestClient(make_app(auth_enabled=True))

    assert client.get("/health").status_code == 200


def test_auth_enabled_with_empty_token_denies_everything():
    """Fail-closed: misconfig ⇒ chặn, không mở toang."""
    client = TestClient(make_app(auth_enabled=True, api_token=""))

    assert client.get("/documents/status", headers={API_KEY_HEADER: ""}).status_code == 401
    assert client.get("/documents/status", headers={API_KEY_HEADER: TOKEN}).status_code == 401
    assert client.get("/health").status_code == 200  # public vẫn phải sống để healthcheck báo lỗi cấu hình


def test_401_response_carries_request_id_header():
    client = TestClient(make_app(auth_enabled=True))

    response = client.get("/documents/status")

    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]


def test_401_keeps_client_request_id_when_request_id_middleware_is_outside():
    """Regression KB-5.5: auth phải được đặt **trong** `RequestIDMiddleware`.

    Lần đầu mình thêm `ApiKeyMiddleware` **sau** `RequestIDMiddleware` ⇒ auth thành lớp ngoài cùng, chạy trước
    khi `request_id` được gán ⇒ 401 trả `request_id: "-"` và header `X-Request-ID: -` (mất trace).
    Test dựng đúng thứ tự như `app/main.py`: `add_middleware(ApiKey)` rồi `add_middleware(RequestID)`.
    """
    from app.core.middleware import RequestIDMiddleware

    settings = SimpleNamespace(auth_enabled=True, api_token=TOKEN)
    app = FastAPI()
    app.add_middleware(ApiKeyMiddleware, settings_provider=lambda: settings)
    app.add_middleware(RequestIDMiddleware)  # thêm sau ⇒ lớp ngoài (đúng thứ tự ở main.py)

    @app.get("/documents/status")
    async def status():
        return {"ok": True}

    response = TestClient(app).get("/documents/status", headers={"X-Request-ID": "trace-123"})

    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == "trace-123"
    assert response.json()["error"]["request_id"] == "trace-123"


def test_unauthorized_error_class_matches_contract():
    error = UnauthorizedError()

    assert (error.code, error.http_status) == ("unauthorized", 401)


@pytest.mark.parametrize("path", ["/chat", "/chat/stream", "/documents/sync", "/conversations", "/ready"])
def test_protected_paths_are_not_public(path):
    assert is_public_path(path) is False
