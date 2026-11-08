"""Test `POST /chat/stream` ở tầng HTTP (KB-3.5, bảo vệ KB-3.3).

Fake service ⇒ không cần LLM/Chroma. Đọc SSE bằng cách tách frame `data: {...}` và bỏ comment `:`.
"""
import json

from app.core.errors import ProviderRateLimitError
from app.core.sse import SSE_HEADERS

PROVIDER_URL = "https://api.groq.com/openai/v1"


def parse_stream(text):
    """Tách body SSE thành list event dict (bỏ heartbeat comment)."""
    events = []
    for part in text.split("\n\n"):
        if not part.startswith("data: "):
            continue  # bỏ comment `: ping`
        events.append(json.loads(part[len("data: "):]))
    return events


def test_stream_emits_start_tokens_then_end(api_client):
    response = api_client.post("/chat/stream", json={"message": "xin chao", "conversation_id": "conv-1"})

    assert response.status_code == 200
    events = parse_stream(response.text)
    assert [event["type"] for event in events] == ["start", "token", "token", "end"]
    assert events[-1]["answer"] == "Xin chao"


def test_stream_sets_antbuffer_headers(api_client):
    response = api_client.post("/chat/stream", json={"message": "xin chao"})

    assert response.headers["content-type"].startswith("text/event-stream")
    for key, value in SSE_HEADERS.items():
        assert response.headers[key.lower()] == value


def test_stream_forwards_request_id_to_service(api_client, fake_chat_service):
    response = api_client.post(
        "/chat/stream", json={"message": "xin chao"}, headers={"X-Request-ID": "kb-3.5-stream-1"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "kb-3.5-stream-1"
    assert fake_chat_service.stream_calls[0]["request_id"] == "kb-3.5-stream-1"


def test_stream_reports_error_event_when_service_fails(api_client, fake_chat_service):
    fake_chat_service.error = ProviderRateLimitError(f"RateLimitError: 429 {PROVIDER_URL}")

    response = api_client.post("/chat/stream", json={"message": "xin chao"})
    events = parse_stream(response.text)

    # Header 200 đã gửi ⇒ lỗi phải là event, stream vẫn kết thúc bình thường
    assert response.status_code == 200
    assert [event["type"] for event in events] == ["error"]
    payload = events[0]["error"]
    assert payload["code"] == "provider_rate_limited"
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert PROVIDER_URL not in response.text
    assert "Traceback" not in response.text
