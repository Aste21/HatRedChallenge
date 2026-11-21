import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.config import get_settings
from app.storage.schema import add_account_column

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages (conversation_id, id);
"""


class StoredMessage(BaseModel):
    """A message as persisted in the chat history."""

    role: Literal["user", "assistant"]
    content: str
    created_at: str


class ConversationSummary(BaseModel):
    """Conversation metadata shown in the history list."""

    id: str
    title: str
    created_at: str
    updated_at: str


class Conversation(ConversationSummary):
    """A conversation including all of its messages, oldest first."""

    messages: list[StoredMessage]


def _to_iso(timestamp: datetime) -> str:
    """Format a UTC timestamp as ISO-8601 with a `Z` suffix.

    Args:
        timestamp: Timezone-aware UTC timestamp.

    Returns:
        The formatted timestamp, e.g. `2026-11-21T09:30:00.123456Z`.
    """
    return timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")


class ConversationRepository:
    """SQLite-backed store for chat conversations; the only module that knows the storage format."""

    def __init__(self, database_path: Path) -> None:
        """Create the database file and schema if they do not exist yet.

        Args:
            database_path: Location of the SQLite file.
        """
        self._database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            add_account_column(connection, "conversations")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a short-lived connection that commits on success and rolls back on error.

        Returns:
            A context manager yielding the connection.
        """
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def list_conversations(self, account_id: str, limit: int = 50) -> list[ConversationSummary]:
        """List the account's most recently active conversations.

        Args:
            account_id: The signed-in account.
            limit: Maximum number of conversations to return.

        Returns:
            Conversation summaries, most recently updated first.
        """
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, title, created_at, updated_at FROM conversations "
                "WHERE account_id = ? ORDER BY updated_at DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        return [ConversationSummary(**dict(row)) for row in rows]

    def get_conversation(self, account_id: str, conversation_id: str) -> Conversation | None:
        """Load one of the account's conversations with all of its messages.

        Args:
            account_id: The signed-in account.
            conversation_id: Id of the conversation.

        Returns:
            The conversation, or `None` if it does not exist or belongs to another account.
        """
        with self._connect() as connection:
            conversation_row = connection.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ? AND account_id = ?",
                (conversation_id, account_id),
            ).fetchone()
            if conversation_row is None:
                return None
            message_rows = connection.execute(
                "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        return Conversation(
            **dict(conversation_row),
            messages=[StoredMessage(**dict(row)) for row in message_rows],
        )

    def create_conversation(self, account_id: str, title: str) -> ConversationSummary:
        """Create an empty conversation for the account.

        Args:
            account_id: The signed-in account.
            title: Human-readable heading for the history list.

        Returns:
            The new conversation's summary.
        """
        now = _to_iso(datetime.now(UTC))
        summary = ConversationSummary(id=uuid.uuid4().hex, title=title, created_at=now, updated_at=now)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at, account_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (summary.id, summary.title, summary.created_at, summary.updated_at, account_id),
            )
        return summary

    def append_exchange(self, conversation_id: str, question: str, reply: str) -> None:
        """Store a user question and the assistant's reply in one transaction.

        Args:
            conversation_id: Id of an existing conversation.
            question: The user's message.
            reply: The assistant's answer.

        Steps:
            1. Insert both messages with the current UTC timestamp.
            2. Bump the conversation's `updated_at` so it moves to the top of the history.
        """
        now = _to_iso(datetime.now(UTC))
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                [(conversation_id, "user", question, now), (conversation_id, "assistant", reply, now)],
            )
            connection.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))

    def delete_conversation(self, account_id: str, conversation_id: str) -> bool:
        """Delete one of the account's conversations and its messages.

        Args:
            account_id: The signed-in account.
            conversation_id: Id of the conversation.

        Returns:
            `True` if something was deleted.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE id = ? AND account_id = ?", (conversation_id, account_id)
            )
        return cursor.rowcount > 0


@lru_cache
def get_conversation_repository() -> ConversationRepository:
    """Create the repository once per process.

    Returns:
        The shared conversation repository.
    """
    return ConversationRepository(get_settings().database_path)
