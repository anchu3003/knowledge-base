"""Lưu bền lịch sử hội thoại bằng SQLite (KB-5.2 — trả TD-2).

Trước KB-5.2, `ChatService.conversations` chỉ nằm trong RAM ⇒ restart container là mất mạch
hội thoại và `conversation_id` cũ trỏ vào state đã mất (câu hỏi follow-up mất context).

Vì sao **SQLite stdlib** (`sqlite3`) thay vì SQLModel/SQLAlchemy (Q&A KB-5.2 Q1):
- 1 người dùng, dữ liệu chỉ là danh sách message ⇒ ORM là over-engineer (AGENTS.md §3.4);
- `sqlite3` có sẵn trong Python ⇒ không thêm dependency nào;
- vẫn có transaction + `PRAGMA journal_mode=WAL` ⇒ đọc trong lúc ghi, không hỏng file khi kill container.

Vì sao **1 file DB riêng** (không nhét vào ChromaDB): Chroma lưu vector, không phải bảng quan hệ;
trộn metadata chat vào đó sẽ khoá chặt ta vào implementation của vector store.

Ghi chú thiết kế:
- Mỗi lần `save()` **thay toàn bộ** message của 1 conversation trong **một transaction** — khớp cách
  `ChatService` giữ list trong RAM (RAM là nguồn của phiên hiện tại, DB là bản bền).
- `prune()` giữ tối đa `max_conversations` (mặc định 200) ⇒ DB không phình vô hạn.
- Mọi method tự mở/đóng connection ⇒ an toàn khi gọi từ thread khác.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Độ dài title lấy từ câu hỏi đầu tiên (giống `deriveTitle` của FE — KB-4.9).
TITLE_MAX_LENGTH = 60


def derive_conversation_title(messages: List[Dict[str, Any]]) -> str:
    """Title = 60 ký tự đầu của câu hỏi user đầu tiên (whitespace gộp lại)."""
    for message in messages:
        if message.get("role") != "user":
            continue
        text = " ".join(str(message.get("content", "")).split())
        if not text:
            continue
        return text if len(text) <= TITLE_MAX_LENGTH else f"{text[:TITLE_MAX_LENGTH - 3]}..."


class ConversationStore:
    """Kho lịch sử hội thoại bền trên SQLite (1 file)."""

    def __init__(self, db_path: str, max_conversations: int = 200) -> None:
        self.db_path = db_path
        self.max_conversations = max(1, int(max_conversations))
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ---------------------------------------------------------------- plumbing

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # WAL: đọc không bị chặn khi đang ghi; busy_timeout: chờ thay vì lỗi "database is locked".
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role            TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    timestamp       TEXT NOT NULL,
                    interrupted     INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id, id);
                CREATE INDEX IF NOT EXISTS idx_conversations_updated
                    ON conversations(updated_at DESC);
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()

    # ---------------------------------------------------------------- API

    def save(self, conversation_id: str, messages: List[Dict[str, Any]]) -> None:
        """Ghi đè toàn bộ message của 1 conversation (upsert + replace, 1 transaction)."""
        if not conversation_id:
            return
        now = self._now()
        title = derive_conversation_title(messages)

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT created_at FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (conversation_id, title, now, now),
                )
            else:
                # Title chỉ tính lại khi suy ra được (giữ title cũ nếu list message rỗng).
                conn.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                    (title or self._title_of(conn, conversation_id), now, conversation_id),
                )

            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.executemany(
                "INSERT INTO messages (conversation_id, role, content, timestamp, interrupted) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        conversation_id,
                        str(message.get("role", "user")),
                        str(message.get("content", "")),
                        str(message.get("timestamp") or now),
                        1 if message.get("interrupted") else 0,
                    )
                    for message in messages
                ],
            )
            self._prune(conn)

    @staticmethod
    def _title_of(conn: sqlite3.Connection, conversation_id: str) -> str:
        row = conn.execute("SELECT title FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return row["title"] if row else ""

    def _prune(self, conn: sqlite3.Connection) -> None:
        """Giữ `max_conversations` conversation mới nhất, xoá phần còn lại (cascade xoá messages)."""
        rows = conn.execute(
            "SELECT id FROM conversations ORDER BY updated_at DESC, id DESC LIMIT -1 OFFSET ?",
            (self.max_conversations,),
        ).fetchall()
        if not rows:
            return
        conn.executemany("DELETE FROM conversations WHERE id = ?", [(row["id"],) for row in rows])
        logger.info("Pruned %d conversation(s) beyond limit=%d", len(rows), self.max_conversations)

    def load(self, conversation_id: str) -> Optional[List[Dict[str, Any]]]:
        """Trả messages của conversation, `None` nếu conversation không tồn tại."""
        with self._connect() as conn:
            found = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if found is None:
                return None
            rows = conn.execute(
                "SELECT role, content, timestamp, interrupted FROM messages "
                "WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()

        messages: List[Dict[str, Any]] = []
        for row in rows:
            message: Dict[str, Any] = {
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
            }
            if row["interrupted"]:
                message["interrupted"] = True
            messages.append(message)
        return messages

    def list(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Danh sách conversation (mới nhất trước) — không kèm messages."""
        query = (
            "SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id) AS message_count "
            "FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id "
            "GROUP BY c.id ORDER BY c.updated_at DESC, c.id DESC"
        )
        params: tuple = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (int(limit),)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": row["message_count"],
            }
            for row in rows
        ]

    def delete(self, conversation_id: str) -> bool:
        """Xoá conversation + messages (ON DELETE CASCADE). Trả `True` nếu có gì bị xoá."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            return cursor.rowcount > 0

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM conversations").fetchone()
        return int(row["n"])

    def close(self) -> None:
        """Gộp WAL vào file chính khi shutdown (không giữ connection thường trực nên không cần đóng)."""
        if self.db_path == ":memory:":
            return
        try:
            with self._connect() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error as exc:  # pragma: no cover - chỉ log, không chặn shutdown
            logger.warning("Conversation store checkpoint failed: %s", exc)

