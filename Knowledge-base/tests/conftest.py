"""Fixture dùng chung cho test tầng HTTP (KB-3.5).

Nguyên tắc: **không** chạy `lifespan`, **không** load model/Chroma, **không** gọi mạng —
service thật được thay bằng fake qua `app.dependency_overrides`.

Vì `TestClient`/`httpx.ASGITransport` **không** chạy lifespan, các biến toàn cục
`document_service`/`chat_service` vẫn là `None` ⇒ test nào cần chúng (vd `/ready`) phải
override dependency hoặc monkeypatch toàn cục một cách tường minh.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_chat_service, get_document_service
from app.services.health_service import HealthService

PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "system_prompt.txt"
FAKE_KEY = "gsk_fake_key_for_tests"


class FakeSecret:
    """Giống `SecretStr` — đủ để test code đọc `.get_secret_value()`."""

    def __init__(self, value: str):
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


def make_fake_settings(**overrides):
    values = dict(
        app_version="1.0.0",
        openai_api_key=FakeSecret(FAKE_KEY),
        openai_model="fake-model",
        openai_base_url="http://localhost:1234/v1",
        system_prompt_path=str(PROMPT_FILE),
    )
    values.update(overrides)
    return type("FakeSettings", (), values)()


class FakeChatService:
    """Fake `ChatService`: trả answer/sources cố định, stream 4 event; `error` để test lỗi."""

    def __init__(self, error=None):
        self.error = error
        self.chat_calls = []
        self.stream_calls = []

    async def chat(self, message, conversation_id=None, max_tokens=None, temperature=None):
        if self.error is not None:
            raise self.error
        self.chat_calls.append({"message": message, "conversation_id": conversation_id})
        return {
            "answer": f"echo: {message}",
            "conversation_id": conversation_id or "conv-fixed",
            "sources": [{
                "citation_id": "S1",
                "chunk_id": "chunk-1",
                "file_path": "Interview/a.md",
                "file_name": "a.md",
                "snippet": "…",
            }],
            "metadata": {"retrieved_documents": 1},
        }

    async def stream_chat(
            self, message, conversation_id=None, max_tokens=None, temperature=None, request_id=None,
    ):
        self.stream_calls.append({"message": message, "request_id": request_id})
        if self.error is not None:
            raise self.error
        conversation_id = conversation_id or "conv-fixed"
        yield {"type": "start", "conversation_id": conversation_id, "metadata": {}}
        yield {"type": "token", "token": "Xin "}
        yield {"type": "token", "token": "chao"}
        yield {
            "type": "end",
            "answer": "Xin chao",
            "conversation_id": conversation_id,
            "sources": [],
            "metadata": {},
        }


class FakeCollection:
    """Fake Chroma collection — `count()` là thứ `/ready` dùng."""

    def __init__(self, owner):
        self._owner = owner

    def count(self) -> int:
        return self._owner.count


class FakeDocumentService:
    """Fake `DocumentService`: status/refresh/clear cố định; `error` để test lỗi."""

    def __init__(self, count: int = 7, error=None):
        self.count = count
        self.error = error
        self.calls = []
        self.collection = FakeCollection(self)

    async def get_status(self):
        self.calls.append("get_status")
        if self.error is not None:
            raise self.error
        return {
            "collection_name": "documents",
            "document_count": self.count,
            "status": "healthy" if self.count else "empty",
        }

    async def auto_load_documents(self):
        self.calls.append("auto_load_documents")
        if self.error is not None:
            raise self.error
        return {
            "processed_files": 2,
            "total_chunks": 7,
            "details": [{"file": "a.md"}, {"file": "b.md"}],
        }

    async def clear_database(self):
        self.calls.append("clear_database")
        if self.error is not None:
            raise self.error
        self.count = 0


@pytest.fixture
def fake_chat_service() -> FakeChatService:
    return FakeChatService()


@pytest.fixture
def fake_document_service() -> FakeDocumentService:
    return FakeDocumentService()


@pytest.fixture
def api_client(fake_chat_service, fake_document_service):
    """`TestClient` với service giả — **không** chạy lifespan, override dọn sau mỗi test."""
    app.dependency_overrides[get_chat_service] = lambda: fake_chat_service
    app.dependency_overrides[get_document_service] = lambda: fake_document_service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def health_service_factory():
    """Tạo `HealthService` với settings giả (để test `/ready` không phụ thuộc `.env`)."""

    def _make(**overrides) -> HealthService:
        return HealthService(make_fake_settings(**overrides))

    return _make
