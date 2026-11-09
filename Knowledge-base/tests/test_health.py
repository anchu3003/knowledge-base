"""Test `/health` (liveness) + `/ready` (readiness) — KB-3.4.

Không cần Chroma/LLM: fake settings + fake collection; `TestClient` không dùng context manager
nên lifespan không chạy (không load model).
"""
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ProviderUnavailableError
from app.main import app, get_health_service
from app.models.schemas import ReadinessResponse
from app.services.health_service import HealthService

PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "system_prompt.txt"
FAKE_KEY = "gsk_fake_key_for_tests"


class FakeSecret:
    def __init__(self, value: str):
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


def make_settings(**overrides) -> SimpleNamespace:
    values = dict(
        app_version="1.0.0",
        openai_api_key=FakeSecret(FAKE_KEY),
        openai_model="fake-model",
        openai_base_url="http://localhost:1234/v1",
        system_prompt_path=str(PROMPT_FILE),
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeCollection:
    def __init__(self, count: int = 3, error: Exception = None):
        self._count = count
        self._error = error

    def count(self) -> int:
        if self._error is not None:
            raise self._error
        return self._count


def make_document_service(count: int = 3, error: Exception = None) -> SimpleNamespace:
    return SimpleNamespace(collection=FakeCollection(count, error))


def readiness(service: HealthService, **kwargs):
    return asyncio.run(service.readiness(**kwargs))


# ------------------------------
# 1. Liveness
# ------------------------------
def test_liveness_is_ok_and_carries_version_and_uptime():
    payload = HealthService(make_settings()).liveness()

    assert payload["status"] == "ok"
    assert payload["version"] == "1.0.0"
    assert payload["uptime_seconds"] >= 0


# ------------------------------
# 2. Readiness: 3 trạng thái
# ------------------------------
def test_readiness_ok_when_all_checks_pass():
    service = HealthService(make_settings())

    payload, http_status = readiness(service, document_service=make_document_service(7))

    assert http_status == 200
    assert payload["status"] == "ok"
    assert set(payload["checks"]) == {"provider_config", "prompt_file", "collection"}
    assert all(check["ok"] for check in payload["checks"].values())
    assert payload["checks"]["collection"]["detail"] == "7 chunks indexed"


def test_readiness_degraded_when_collection_is_empty():
    service = HealthService(make_settings())

    payload, http_status = readiness(service, document_service=make_document_service(0))

    assert http_status == 200  # AC: vẫn nhận request
    assert payload["status"] == "degraded"
    assert payload["checks"]["collection"]["ok"] is False
    assert payload["checks"]["provider_config"]["ok"] is True


def test_readiness_degraded_when_collection_raises_without_leaking_detail():
    service = HealthService(make_settings())

    payload, http_status = readiness(
        service, document_service=make_document_service(error=RuntimeError("chroma secret path /tmp/x"))
    )

    assert http_status == 200
    assert payload["status"] == "degraded"
    assert payload["checks"]["collection"] == {"ok": False, "detail": "collection unavailable"}


def test_readiness_error_when_api_key_missing():
    service = HealthService(make_settings(openai_api_key=FakeSecret("")))

    payload, http_status = readiness(service, document_service=make_document_service(7))

    assert http_status == 503
    assert payload["status"] == "error"
    assert payload["checks"]["provider_config"]["ok"] is False
    assert "OPENAI_API_KEY" in payload["checks"]["provider_config"]["detail"]


def test_readiness_ok_when_prompt_file_missing_uses_fallback(tmp_path):
    """KB-5.9 (trả TD-19): thiếu prompt file **không** làm `/ready` đỏ — ChatService có fallback trong code."""
    missing = tmp_path / "system_prompt.txt"
    service = HealthService(make_settings(system_prompt_path=str(missing)))

    payload, http_status = readiness(service, document_service=make_document_service(7))

    assert http_status == 200
    assert payload["status"] == "ok"
    assert payload["checks"]["prompt_file"]["ok"] is True
    assert "fallback" in payload["checks"]["prompt_file"]["detail"]
    assert "system_prompt.txt" in payload["checks"]["prompt_file"]["detail"]


def test_readiness_ok_when_prompt_path_not_set():
    """`SYSTEM_PROMPT_PATH` rỗng cũng chỉ là thông tin — không phải lỗi."""
    service = HealthService(make_settings(system_prompt_path=None))

    payload, http_status = readiness(service, document_service=make_document_service(7))

    assert http_status == 200
    assert payload["checks"]["prompt_file"]["ok"] is True
    assert "fallback" in payload["checks"]["prompt_file"]["detail"]


# ------------------------------
# 3. `deep=true`: mặc định KHÔNG gọi provider
# ------------------------------
class CountingProbe:
    def __init__(self, error: Exception = None):
        self.calls = 0
        self.error = error

    async def __call__(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return "pong"


def test_default_readiness_never_calls_provider():
    service = HealthService(make_settings())
    probe = CountingProbe(error=AssertionError("không được gọi provider khi deep=False"))

    payload, http_status = readiness(service, document_service=make_document_service(7), provider_probe=probe)

    assert payload["status"] == "ok"
    assert "provider" not in payload["checks"]
    assert probe.calls == 0
    assert http_status == 200


def test_deep_readiness_calls_provider_once():
    service = HealthService(make_settings())
    probe = CountingProbe()

    payload, http_status = readiness(
        service, document_service=make_document_service(7), provider_probe=probe, deep=True,
    )

    assert probe.calls == 1
    assert http_status == 200
    assert payload["status"] == "ok"
    assert payload["checks"]["provider"]["ok"] is True


def test_deep_readiness_returns_503_when_provider_fails():
    service = HealthService(make_settings())
    probe = CountingProbe(ProviderUnavailableError("APIConnectionError: dns api.groq.com"))

    payload, http_status = readiness(
        service, document_service=make_document_service(7), provider_probe=probe, deep=True,
    )

    assert http_status == 503
    assert payload["status"] == "error"
    assert payload["checks"]["provider"]["ok"] is False
    assert payload["checks"]["provider"]["detail"] == "provider call failed: provider_unavailable"
    assert "api.groq.com" not in str(payload)  # không lộ chi tiết nội bộ


def test_deep_readiness_without_initialized_service_is_503():
    service = HealthService(make_settings())

    payload, http_status = readiness(service, document_service=make_document_service(7), deep=True)

    assert http_status == 503
    assert payload["checks"]["provider"] == {"ok": False, "detail": "provider not initialized"}


# ------------------------------
# 4. HTTP: /health, /ready, / không đổi
# ------------------------------
def test_http_health_is_ok_without_services():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body and "uptime_seconds" in body


def test_http_ready_reports_degraded_when_document_service_not_initialized():
    response = TestClient(app).get("/ready")
    body = response.json()

    assert response.status_code == 200  # degraded, không phải lỗi cấu hình
    assert body["status"] == "degraded"
    assert body["checks"]["collection"]["detail"] == "document service not initialized"
    ReadinessResponse(**body)  # khớp schema công bố


def test_http_ready_returns_503_with_broken_provider_config():
    broken = HealthService(make_settings(openai_api_key=FakeSecret("")))
    app.dependency_overrides[get_health_service] = lambda: broken
    try:
        response = TestClient(app).get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["status"] == "error"


def test_http_root_endpoint_contract_unchanged():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "message": "RAG Chatbot API is running",
        "version": "1.0.0",
    }


def test_readiness_error_is_logged_at_warning(caplog):
    caplog.set_level(logging.WARNING)
    service = HealthService(make_settings(openai_api_key=FakeSecret("")))

    readiness(service, document_service=make_document_service(7))

    assert "readiness failed" in caplog.text
    assert "provider_config" in caplog.text
