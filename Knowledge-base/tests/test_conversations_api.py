"""Test HTTP cho `/conversations*` (KB-5.2) — dùng `FakeChatService`, không chạm SQLite/LLM.

Dùng fixture `api_client` của `conftest` (**không** chạy lifespan ⇒ không load model, test nhanh).
"""

import pytest
from fastapi.testclient import TestClient

import app.core.errors as errors
import app.main as main_module
from app.main import get_chat_service
from tests.conftest import FakeChatService

CONVERSATIONS = {
    "conv-1": [
        {"role": "user", "content": "Kafka là gì?", "timestamp": "2026-01-01T00:00:00"},
        {"role": "assistant", "content": "Message broker.", "timestamp": "2026-01-01T00:00:00"},
    ],
    "conv-2": [
        {"role": "user", "content": "RabbitMQ?", "timestamp": "2026-01-01T00:00:00"},
    ],
}


@pytest.fixture
def client(fake_chat_service):
    """`api_client` nhưng chat service có sẵn lịch sử."""
    fake_chat_service.conversations = {key: list(value) for key, value in CONVERSATIONS.items()}
    main_module.app.dependency_overrides[get_chat_service] = lambda: fake_chat_service
    try:
        yield TestClient(main_module.app)
    finally:
        main_module.app.dependency_overrides.clear()


def test_list_conversations(client):
    response = client.get("/conversations")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["conversations"]} == {"conv-1", "conv-2"}
    assert next(i for i in body["conversations"] if i["id"] == "conv-1")["message_count"] == 2


def test_list_conversations_when_empty(api_client):
    response = api_client.get("/conversations")

    assert response.status_code == 200
    assert response.json() == {"conversations": [], "total": 0}


def test_get_conversation_detail(client):
    response = client.get("/conversations/conv-1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "conv-1"
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]
    assert body["messages"][1]["content"] == "Message broker."


def test_get_unknown_conversation_returns_404(client):
    response = client.get("/conversations/khong-co")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["message"]  # contract: message công khai, không lộ chi tiết nội bộ
    assert error["request_id"]


def test_delete_conversation(client):
    response = client.delete("/conversations/conv-2")

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conv-2"
    # xoá thật: lần đọc sau trả 404
    assert client.get("/conversations/conv-2").status_code == 404
    assert client.get("/conversations").json()["total"] == 1


def test_delete_unknown_conversation_returns_404(client):
    response = client.delete("/conversations/khong-co")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_store_error_maps_to_500():
    service = FakeChatService(error=errors.ConversationStoreError("boom"))
    main_module.app.dependency_overrides[get_chat_service] = lambda: service
    try:
        response = TestClient(main_module.app).get("/conversations")
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "conversation_store_error"
