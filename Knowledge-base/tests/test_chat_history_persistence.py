"""Test tích hợp `ChatService` + `ConversationStore` (KB-5.2).

Mục tiêu chính = AC1: **restart** (tạo `ChatService` mới, RAM rỗng) vẫn giữ được lịch sử ⇒ câu hỏi
follow-up có context. Không gọi mạng: không `chat()` thật, chỉ ghi/đọc history.
"""

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.chat_service import ChatService
from app.services.conversation_store import ConversationStore


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-key-for-tests")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "chat.db"))
    return Settings()


def _service(settings) -> ChatService:
    store = ConversationStore(settings.chat_db_path, settings.max_conversations)
    return ChatService(settings, SimpleNamespace(), conversation_store=store)


def test_history_survives_restart(settings):
    """AC1: service mới (RAM rỗng) vẫn đọc được hội thoại cũ từ SQLite."""
    first = _service(settings)
    first._update_conversation("conv-1", "Kafka là gì?", "Kafka là message broker.")

    restarted = _service(settings)  # RAM trắng ⇒ chỉ còn SQLite

    history = restarted.get_conversation_history("conv-1")
    assert [message["content"] for message in history] == ["Kafka là gì?", "Kafka là message broker."]
    assert [message["role"] for message in history] == ["user", "assistant"]


def test_follow_up_uses_persisted_history_as_context(settings):
    """Context follow-up: `_build_messages` phải thấy lượt trước sau khi restart."""
    first = _service(settings)
    first._update_conversation("conv-1", "Kafka là gì?", "Kafka là message broker.")

    restarted = _service(settings)
    history = restarted.get_conversation_history("conv-1")
    built = restarted._build_messages("system", history, "Còn RabbitMQ thì sao?")

    # system + 2 lượt cũ + câu mới
    assert len(built) == 4
    assert built[3].content == "Còn RabbitMQ thì sao?"


def test_user_message_is_redacted_before_persisting(settings):
    """Giả định (b) KB-5.2: **không lưu PII thô** — PII bị che trước khi vào DB.

    Dùng SĐT **giả** (ghép chuỗi để `tools/pii_scan.py` không báo nhầm — xem TD-11). Không dùng
    `user@example.com` vì redactor bỏ qua `example.*` (KB-1.1), sẽ không chứng minh được gì.
    """
    fake_phone = "0912" "345" "678"
    service = _service(settings)
    service._update_conversation("conv-1", f"Gọi {fake_phone} giúp mình nhé", "Ok.")

    stored = service.conversation_store.load("conv-1")
    assert fake_phone not in stored[0]["content"]
    assert "REDACTED" in stored[0]["content"]


def test_clear_conversation_removes_from_store(settings):
    service = _service(settings)
    service._update_conversation("conv-1", "hỏi", "đáp")

    service.clear_conversation("conv-1")

    assert service.conversation_store.load("conv-1") is None
    assert service.get_conversation_history("conv-1") == []


def test_list_conversations_reads_from_store(settings):
    service = _service(settings)
    service._update_conversation("conv-1", "câu hỏi một", "đáp")
    service._update_conversation("conv-2", "câu hỏi hai", "đáp")

    items = {item["id"]: item for item in service.list_conversations()}

    assert set(items) == {"conv-1", "conv-2"}
    assert items["conv-1"]["message_count"] == 2
    assert items["conv-1"]["title"] == "câu hỏi một"


def test_get_conversation_detail_none_for_unknown(settings):
    service = _service(settings)

    assert service.get_conversation_detail("không-có") is None


def test_works_without_store(settings):
    """Không có store (CHAT_DB_PATH rỗng) ⇒ hành vi cũ: chỉ in-memory, không ném lỗi."""
    service = ChatService(settings, SimpleNamespace(), conversation_store=None)
    service._update_conversation("conv-1", "hỏi", "đáp")

    assert len(service.get_conversation_history("conv-1")) == 2
    assert service.list_conversations()[0]["id"] == "conv-1"


def test_store_failure_does_not_break_answer(settings):
    """Lỗi ghi DB không được làm hỏng câu trả lời đã sinh."""

    class BrokenStore:
        def save(self, *_args, **_kwargs):
            raise RuntimeError("disk full")

        def load(self, *_args, **_kwargs):
            raise RuntimeError("disk full")

    service = ChatService(settings, SimpleNamespace(), conversation_store=BrokenStore())

    service._update_conversation("conv-1", "hỏi", "đáp")  # không raise

    assert len(service.conversations["conv-1"]) == 2
