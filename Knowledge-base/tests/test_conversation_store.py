"""Test `ConversationStore` — lịch sử hội thoại bền bằng SQLite (KB-5.2).

Chỉ chạm đĩa tạm (`tmp_path`), không cần model/Chroma/LLM.
"""

import sqlite3

import pytest

from app.services.conversation_store import ConversationStore, derive_conversation_title


def _messages(*pairs):
    out = []
    for role, content in pairs:
        out.append({"role": role, "content": content, "timestamp": "2026-01-01T00:00:00"})
    return out


def test_save_then_load_round_trip(tmp_path):
    store = ConversationStore(str(tmp_path / "chat.db"))
    messages = _messages(("user", "Kafka là gì?"), ("assistant", "Kafka là message broker."))

    store.save("conv-1", messages)

    assert store.load("conv-1") == messages
    assert store.count() == 1


def test_load_unknown_conversation_returns_none(tmp_path):
    store = ConversationStore(str(tmp_path / "chat.db"))

    assert store.load("không-tồn-tại") is None


def test_save_replaces_messages_of_same_conversation(tmp_path):
    """Ghi đè = mất message cũ (không nhân đôi) — khớp cách `ChatService` ghi cả list mỗi lượt."""
    store = ConversationStore(str(tmp_path / "chat.db"))
    store.save("conv-1", _messages(("user", "câu 1"), ("assistant", "trả lời 1")))
    store.save("conv-1", _messages(("user", "câu 1"), ("assistant", "trả lời 1"), ("user", "câu 2")))

    loaded = store.load("conv-1")
    assert [m["content"] for m in loaded] == ["câu 1", "trả lời 1", "câu 2"]
    assert store.count() == 1


def test_interrupted_flag_is_persisted(tmp_path):
    store = ConversationStore(str(tmp_path / "chat.db"))
    store.save("conv-1", [
        {"role": "user", "content": "hỏi", "timestamp": "t"},
        {"role": "assistant", "content": "dở", "timestamp": "t", "interrupted": True},
    ])

    loaded = store.load("conv-1")
    assert loaded[1]["interrupted"] is True
    assert "interrupted" not in loaded[0]


def test_title_from_first_user_message(tmp_path):
    store = ConversationStore(str(tmp_path / "chat.db"))
    store.save("conv-1", _messages(("user", "   So sánh   Kafka\nvà RabbitMQ  "), ("assistant", "…")))

    assert store.list()[0]["title"] == "So sánh Kafka và RabbitMQ"


def test_title_is_truncated():
    title = derive_conversation_title([{"role": "user", "content": "x" * 100}])

    assert title.endswith("...")
    assert len(title) == 60


def test_list_newest_first_with_message_count(tmp_path):
    store = ConversationStore(str(tmp_path / "chat.db"))
    store.save("conv-a", _messages(("user", "a"), ("assistant", "b")))
    store.save("conv-b", _messages(("user", "c")))
    # ép updated_at của conv-b mới hơn conv-a (thứ tự thật phụ thuộc đồng hồ)
    with sqlite3.connect(str(tmp_path / "chat.db")) as conn:
        conn.execute("UPDATE conversations SET updated_at = '2099-01-01T00:00:00' WHERE id = 'conv-b'")

    items = store.list()

    assert [item["id"] for item in items] == ["conv-b", "conv-a"]
    assert items[0]["message_count"] == 1
    assert items[1]["message_count"] == 2


def test_list_unknown_db_is_empty(tmp_path):
    assert ConversationStore(str(tmp_path / "chat.db")).list() == []


def test_delete_removes_conversation_and_messages(tmp_path):
    store = ConversationStore(str(tmp_path / "chat.db"))
    store.save("conv-1", _messages(("user", "a"), ("assistant", "b")))

    assert store.delete("conv-1") is True
    assert store.load("conv-1") is None
    assert store.count() == 0
    with sqlite3.connect(str(tmp_path / "chat.db")) as conn:
        remaining = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert remaining == 0  # cascade, không để message mồ côi


def test_delete_unknown_returns_false(tmp_path):
    assert ConversationStore(str(tmp_path / "chat.db")).delete("không-có") is False


def test_prune_keeps_only_max_conversations(tmp_path):
    store = ConversationStore(str(tmp_path / "chat.db"), max_conversations=2)
    for index in range(4):
        store.save(f"conv-{index}", _messages(("user", f"câu {index}")))
        with sqlite3.connect(str(tmp_path / "chat.db")) as conn:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (f"2026-01-0{index + 1}T00:00:00", f"conv-{index}"),
            )

    items = store.list()

    assert store.count() == 2
    assert [item["id"] for item in items] == ["conv-3", "conv-2"]  # giữ mới nhất


def test_survives_new_store_instance(tmp_path):
    """Mô phỏng restart: instance mới (process mới) đọc lại đúng dữ liệu cũ."""
    path = str(tmp_path / "chat.db")
    ConversationStore(path).save("conv-1", _messages(("user", "còn đây không?")))

    reopened = ConversationStore(path)

    assert reopened.load("conv-1")[0]["content"] == "còn đây không?"


def test_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "chat.db"

    ConversationStore(str(path)).save("conv-1", _messages(("user", "x")))

    assert path.exists()


def test_save_with_empty_id_is_ignored(tmp_path):
    store = ConversationStore(str(tmp_path / "chat.db"))

    store.save("", _messages(("user", "x")))

    assert store.count() == 0


def test_reopening_does_not_recreate_schema(tmp_path):
    """`CREATE TABLE IF NOT EXISTS` ⇒ mở lại nhiều lần không lỗi và không mất dữ liệu."""
    path = str(tmp_path / "chat.db")
    store = ConversationStore(path)
    store.save("conv-1", _messages(("user", "x")))

    for _ in range(3):
        ConversationStore(path)

    assert store.load("conv-1") is not None
