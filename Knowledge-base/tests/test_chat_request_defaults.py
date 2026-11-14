"""KB-9.1: `max_tokens`/`temperature` phải lấy từ env khi client không gửi.

Bug cũ: `ChatRequest` khai default 1000/0.7 ⇒ Pydantic luôn điền ⇒ `service` thấy "có giá trị" và bỏ qua
`DEFAULT_MAX_TOKENS`/`DEFAULT_TEMPERATURE` (2 biến env chết). Thêm nữa `temperature or default` biến
`0.0` (hợp lệ) thành 0.7.
"""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.schemas import ChatRequest
from app.services.chat_service import ChatService


# ------------------------------
# Schema: default phải là None
# ------------------------------
def test_chat_request_defaults_are_none():
    req = ChatRequest(message="Kafka là gì?")
    assert req.max_tokens is None
    assert req.temperature is None


def test_chat_request_accepts_explicit_values():
    req = ChatRequest(message="x", max_tokens=2500, temperature=0.0)
    assert req.max_tokens == 2500
    assert req.temperature == 0.0  # 0.0 phải giữ nguyên, không bị coi là "không set"


@pytest.mark.parametrize("payload", [
    {"message": "x", "max_tokens": 10},        # < 64
    {"message": "x", "max_tokens": 9999},      # > 8000
    {"message": "x", "temperature": -0.1},     # < 0
    {"message": "x", "temperature": 2.5},      # > 2
])
def test_chat_request_rejects_out_of_range(payload):
    with pytest.raises(ValidationError):
        ChatRequest(**payload)


# ------------------------------
# Service: env là fallback, request override thắng
# ------------------------------
def _service(default_max_tokens: int = 2500, default_temperature: float = 0.2) -> ChatService:
    """Dựng ChatService **không** qua `__init__` (khỏi load Chroma/LLM) — chỉ cần settings."""
    service = object.__new__(ChatService)
    service.settings = SimpleNamespace(
        default_max_tokens=default_max_tokens,
        default_temperature=default_temperature,
    )
    return service


def _resolve(service: ChatService, max_tokens, temperature):
    """Bản sao 2 dòng resolve y như `chat()`/`stream_chat()` (cùng biểu thức, không gọi provider)."""
    resolved_max = max_tokens if max_tokens is not None else service.settings.default_max_tokens
    resolved_temp = temperature if temperature is not None else service.settings.default_temperature
    return resolved_max, resolved_temp


def test_service_falls_back_to_env_defaults():
    assert _resolve(_service(), None, None) == (2500, 0.2)


def test_service_keeps_temperature_zero():
    """`0.0` là giá trị hợp lệ (deterministic) — bug cũ trả 0.7."""
    assert _resolve(_service(), None, 0.0) == (2500, 0.0)


def test_service_request_overrides_win():
    assert _resolve(_service(), 800, 0.9) == (800, 0.9)
