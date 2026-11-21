import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.agents.chat.charts import ChartSpec
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
CREATE TABLE IF NOT EXISTS sample_seeds (
    account_id TEXT PRIMARY KEY,
    seeded_at TEXT NOT NULL
);
"""


class StoredMessage(BaseModel):
    """A message as persisted in the chat history; assistant messages may carry a chart."""

    role: Literal["user", "assistant"]
    content: str
    created_at: str
    chart: ChartSpec | None = None


def _add_chart_column(connection: sqlite3.Connection) -> None:
    """Add the `chart` column to a `messages` table created before charts existed.

    Args:
        connection: Open SQLite connection.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)")}
    if "chart" in columns:
        return
    try:
        connection.execute("ALTER TABLE messages ADD COLUMN chart TEXT")
    except sqlite3.OperationalError as error:
        # Two first requests can migrate at the same time; the second one finds the column already added.
        if "duplicate column" not in str(error):
            raise


def _load_chart(raw_chart: str | None) -> ChartSpec | None:
    """Read a stored chart, ignoring one that no longer matches the current chart format.

    Args:
        raw_chart: JSON text from the `chart` column.

    Returns:
        The chart specification, or `None`.
    """
    if not raw_chart:
        return None
    try:
        return ChartSpec.model_validate_json(raw_chart)
    except ValidationError:
        return None


class ConversationSummary(BaseModel):
    """Conversation metadata shown in the history list."""

    id: str
    title: str
    created_at: str
    updated_at: str


class Conversation(ConversationSummary):
    """A conversation including all of its messages, oldest first."""

    messages: list[StoredMessage]


class ConversationDraft(BaseModel):
    """A complete conversation to insert as it is (e.g. a curated sample), dated by its messages."""

    title: str
    messages: list[StoredMessage] = Field(min_length=1)


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
            _add_chart_column(connection)

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
                "SELECT role, content, created_at, chart FROM messages WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        return Conversation(
            **dict(conversation_row),
            messages=[
                StoredMessage(
                    role=row["role"],
                    content=row["content"],
                    created_at=row["created_at"],
                    chart=_load_chart(row["chart"]),
                )
                for row in message_rows
            ],
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

    def append_exchange(
        self, conversation_id: str, question: str, reply: str, chart: ChartSpec | None = None
    ) -> None:
        """Store a user question and the assistant's reply in one transaction.

        Args:
            conversation_id: Id of an existing conversation.
            question: The user's message.
            reply: The assistant's answer.
            chart: The chart shown with the answer, if any.

        Steps:
            1. Insert both messages with the current UTC timestamp, the chart as JSON on the reply.
            2. Bump the conversation's `updated_at` so it moves to the top of the history.
        """
        now = _to_iso(datetime.now(UTC))
        chart_json = chart.model_dump_json() if chart is not None else None
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO messages (conversation_id, role, content, created_at, chart) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (conversation_id, "user", question, now, None),
                    (conversation_id, "assistant", reply, now, chart_json),
                ],
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

    def seed_conversations(self, account_id: str, drafts: list[ConversationDraft]) -> bool:
        """Insert sample conversations once per account, so ones the owner deletes never come back.

        Args:
            account_id: The account the samples belong to.
            drafts: The conversations to insert, with their messages and timestamps.

        Returns:
            `True` if the samples were inserted, `False` if the account had been seeded before.

        Steps:
            1. Record the account in `sample_seeds`; if it is already there, stop.
            2. Insert every draft in the same transaction, so two starting workers never both seed.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO sample_seeds (account_id, seeded_at) VALUES (?, ?)",
                (account_id, _to_iso(datetime.now(UTC))),
            )
            if cursor.rowcount == 0:
                return False
            _insert_drafts(connection, account_id, drafts)
        return True

    def reset_conversations(self, account_id: str, drafts: list[ConversationDraft]) -> None:
        """Replace all of the account's conversations with the given ones (used to prepare a demo).

        Args:
            account_id: The account whose chat history is replaced.
            drafts: The conversations to insert, with their messages and timestamps.

        Steps:
            1. Delete the account's conversations; their messages go with them.
            2. Insert the drafts and mark the account as seeded, all in one transaction.
        """
        with self._connect() as connection:
            connection.execute("DELETE FROM conversations WHERE account_id = ?", (account_id,))
            _insert_drafts(connection, account_id, drafts)
            connection.execute(
                "INSERT OR REPLACE INTO sample_seeds (account_id, seeded_at) VALUES (?, ?)",
                (account_id, _to_iso(datetime.now(UTC))),
            )


def _insert_drafts(connection: sqlite3.Connection, account_id: str, drafts: list[ConversationDraft]) -> None:
    """Insert complete conversations, dated by their first and last message.

    Args:
        connection: Open SQLite connection inside the caller's transaction.
        account_id: The account the conversations belong to.
        drafts: Conversations with at least one message each.
    """
    for draft in drafts:
        conversation_id = uuid.uuid4().hex
        connection.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, account_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                conversation_id,
                draft.title,
                draft.messages[0].created_at,
                draft.messages[-1].created_at,
                account_id,
            ),
        )
        connection.executemany(
            "INSERT INTO messages (conversation_id, role, content, created_at, chart) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    conversation_id,
                    message.role,
                    message.content,
                    message.created_at,
                    message.chart.model_dump_json() if message.chart is not None else None,
                )
                for message in draft.messages
            ],
        )


@lru_cache
def get_conversation_repository() -> ConversationRepository:
    """Create the repository once per process.

    Returns:
        The shared conversation repository.
    """
    return ConversationRepository(get_settings().database_path)
