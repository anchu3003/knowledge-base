"""Test SSE contract (KB-3.3): `start → token* → (end | error)`, heartbeat, disconnect.

Không cần LLM/Chroma/network: fake LLM client + fake event generator + `TestClient`
(không dùng context manager ⇒ lifespan không chạy).
"""
import asyncio
import contextlib
import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import InternalServerError

from app.core.config import Settings
from app.core.errors import ProviderUnavailableError
from app.core.provider_retry import ProviderThrottle
from app.core.sse import HEARTBEAT_COMMENT, SSE_HEADERS, error_event, format_event, sse_event_stream
from app.main import app, get_chat_service
from app.services.chat_service import ChatService
from app.services.pii_service import PIIRedactor

PROVIDER_URL = "https://api.groq.com/openai/v1/chat/completions"


def _request() -> httpx.Request:
    return httpx.Request("POST", PROVIDER_URL)


def _server_error():
    return InternalServerError("upstream blew up", response=httpx.Response(500, request=_request()), body=None)


class SleepRecorder:
    def __init__(self):
        self.delays = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def parse_frames(frames):
    """Bỏ heartbeat comment, trả về list event đã decode."""
    events = []
    for frame in frames:
        if frame.startswith(":"):
            continue
        assert frame.startswith("data: ") and frame.endswith("\n\n")
        events.append(json.loads(frame[len("data: "):].strip()))
    return events


def frame_types(frames):
    return [event["type"] for event in parse_frames(frames)]


async def collect(frames):
    return [frame async for frame in frames]


class FakeDocumentService:
    async def search_similar_documents(self, query, k=3):
        return []


class PartialStreamLLM:
    """Fake LLM: stream vài token rồi raise lỗi provider (mô phỏng lỗi giữa stream)."""

    temperature = 0.0
    max_tokens = 128

    def __init__(self, error, tokens=("Xin ", "chao ")):
        self.error = error
        self.tokens = tokens
        self.calls = 0

    async def agenerate(self, messages):  # pragma: no cover - stream test không dùng
        self.calls += 1
        raise self.error

    async def astream(self, messages):
        self.calls += 1
        for token in self.tokens:
            yield SimpleNamespace(content=token)
        raise self.error


class BlockingStreamLLM:
    """Fake LLM: stream 1 token rồi treo (để test client disconnect)."""

    temperature = 0.0
    max_tokens = 128

    def __init__(self, tokens=("partial ",), block_seconds=5.0):
        self.tokens = tokens
        self.block_seconds = block_seconds

    async def agenerate(self, messages):  # pragma: no cover
        raise AssertionError("không dùng")

    async def astream(self, messages):
        for token in self.tokens:
            yield SimpleNamespace(content=token)
        await asyncio.sleep(self.block_seconds)


def make_chat_service(llm, *, provider_max_retries=0) -> ChatService:
    settings = SimpleNamespace(
        default_max_tokens=128,
        default_temperature=0.0,
        retrieval_k=3,
        enable_query_rewrite=False,
        rewrite_system_prompt_path=None,
        rewrite_min_results=2,
        rewrite_min_top_score=0.3,
        rewrite_max_attempts=2,
        max_conversation_length=10,
        system_prompt_path=None,
        context_max_chars=6000,
        openai_model="fake-model",
        openai_base_url="",
        enable_pii_redaction=True,
        pii_placeholder="[REDACTED:{type}]",
        provider_timeout_seconds=60.0,
        provider_max_retries=provider_max_retries,
        provider_retry_base_delay=2.0,
        provider_max_concurrency=1,
        sse_heartbeat_seconds=15.0,
    )
    service = object.__new__(ChatService)
    service.settings = settings
    service.document_service = FakeDocumentService()
    service.llm = llm
    service.conversations = {}
    service.pii = PIIRedactor(settings)
    service.provider = ProviderThrottle(settings, sleep=SleepRecorder())
    return service


# ------------------------------
# 1. Transport: format + happy path + fallback lỗi + heartbeat
# ------------------------------
def test_format_event_is_sse_frame():
    assert format_event({"type": "token", "token": "é"}) == 'data: {"type": "token", "token": "é"}\n\n'


def test_error_event_uses_chat_envelope_and_hides_internals():
    event = error_event(ProviderUnavailableError(f"APIConnectionError: dns {PROVIDER_URL}"), "req-9")

    assert event == {
        "type": "error",
        "error": {
            "code": "provider_unavailable",
            "message": ProviderUnavailableError.public_message,
            "request_id": "req-9",
        },
    }
    assert PROVIDER_URL not in json.dumps(event)


def test_happy_path_streams_start_tokens_then_end():
    async def events():
        yield {"type": "start", "conversation_id": "c1"}
        yield {"type": "token", "token": "a"}
        yield {"type": "token", "token": "b"}
        yield {"type": "end", "answer": "ab"}

    frames = asyncio.run(collect(sse_event_stream(events(), request_id="r1", heartbeat_seconds=5)))

    assert frame_types(frames) == ["start", "token", "token", "end"]
    assert "error" not in frame_types(frames)


def test_exception_escaping_the_service_becomes_error_event_then_closes():
    async def events():
        yield {"type": "start", "conversation_id": "c1"}
        raise ProviderUnavailableError(f"APIConnectionError: dns {PROVIDER_URL}")

    frames = asyncio.run(collect(sse_event_stream(events(), request_id="r2", heartbeat_seconds=5)))
    parsed = parse_frames(frames)

    assert [event["type"] for event in parsed] == ["start", "error"]
    assert parsed[-1]["error"]["code"] == "provider_unavailable"
    assert parsed[-1]["error"]["request_id"] == "r2"
    assert PROVIDER_URL not in frames[-1]


def test_heartbeat_comment_when_no_event_within_timeout():
    async def events():
        yield {"type": "start", "conversation_id": "c1"}
        await asyncio.sleep(0.2)
        yield {"type": "end", "answer": ""}

    frames = asyncio.run(collect(sse_event_stream(events(), heartbeat_seconds=0.05)))

    assert HEARTBEAT_COMMENT in frames
    assert frame_types(frames) == ["start", "end"]  # ping không làm hỏng thứ tự event


# ------------------------------
# 2. Service: lỗi giữa stream + disconnect (Q&A KB-3.3)
# ------------------------------
def test_error_mid_stream_yields_tokens_then_error_without_end():
    llm = PartialStreamLLM(_server_error())
    service = make_chat_service(llm, provider_max_retries=2)

    async def collect_events():
        return [event async for event in service.stream_chat(message="hello", request_id="req-mid")]

    events = asyncio.run(collect_events())
    types = [event["type"] for event in events]

    assert types == ["start", "token", "token", "error"]
    assert "end" not in types  # contract: `end` và `error` loại trừ nhau
    payload = events[-1]["error"]
    assert payload["code"] == "provider_unavailable"
    assert payload["request_id"] == "req-mid"
    assert PROVIDER_URL not in json.dumps(events)  # không lộ str(e)/URL provider
    assert llm.calls == 1  # đã có token ⇒ không retry giữa stream


def consume_then_cancel(service, conversation_id, *, request_id="req-dc", delay=0.1):
    async def scenario():
        generator = service.stream_chat(message="hi", conversation_id=conversation_id, request_id=request_id)
        received = []

        async def consume():
            async for event in generator:
                received.append(event)

        task = asyncio.create_task(consume())
        await asyncio.sleep(delay)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return received

    return asyncio.run(scenario())


def test_disconnect_saves_partial_answer_marked_interrupted(caplog):
    caplog.set_level(logging.INFO)
    service = make_chat_service(BlockingStreamLLM(tokens=("partial ",)))

    received = consume_then_cancel(service, conversation_id="conv-dc")

    history = service.conversations["conv-dc"]
    assert [event.get("type") for event in received] == ["start", "token"]
    assert history[-1]["role"] == "assistant"
    assert history[-1]["content"] == "partial "
    assert history[-1]["interrupted"] is True
    assert "stream_chat interrupted" in caplog.text
    assert "Traceback" not in caplog.text  # disconnect không phải lỗi → không stack


def test_disconnect_before_first_token_saves_nothing(caplog):
    caplog.set_level(logging.INFO)
    service = make_chat_service(BlockingStreamLLM(tokens=()))

    received = consume_then_cancel(service, conversation_id="conv-dc-empty")

    assert [event.get("type") for event in received] == ["start"]
    assert service.conversations == {}  # chưa có token ⇒ không lưu gì
    assert "nothing saved" in caplog.text
    assert "Traceback" not in caplog.text


# ------------------------------
# 3. HTTP: header chống buffer + contract + request_id
# ------------------------------
class FakeStreamingService:
    def __init__(self):
        self.request_ids = []

    async def stream_chat(self, **kwargs):
        self.request_ids.append(kwargs.get("request_id"))
        yield {"type": "start", "conversation_id": "c1"}
        yield {"type": "token", "token": "hi"}
        yield {"type": "end", "answer": "hi"}


def test_http_stream_sets_antbuffer_headers_and_forwards_request_id():
    service = FakeStreamingService()
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        response = TestClient(app).post("/chat/stream", json={"message": "hi"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    for key, value in SSE_HEADERS.items():
        assert response.headers[key.lower()] == value
    assert response.headers["x-request-id"]
    assert service.request_ids == [response.headers["x-request-id"]]
    events = [
        json.loads(part[len("data: "):])
        for part in response.text.split("\n\n")
        if part.startswith("data: ")
    ]
    assert [event["type"] for event in events] == ["start", "token", "end"]


def test_settings_sse_heartbeat_default(monkeypatch):
    monkeypatch.delenv("SSE_HEARTBEAT_SECONDS", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost")

    assert Settings().sse_heartbeat_seconds == 15.0
