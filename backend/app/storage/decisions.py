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
from app.storage.conversations import _to_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposal_decisions (
    proposal_id TEXT PRIMARY KEY,
    proposal_group TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'declined')),
    title TEXT NOT NULL,
    amount REAL NOT NULL,
    decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS simulated_transactions (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES proposal_decisions(proposal_id),
    kind TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'sent', 'failed')),
    created_at TEXT NOT NULL
);
"""

Decision = Literal["approved", "declined"]
NotificationStatus = Literal["queued", "sent", "failed"]


class StoredDecision(BaseModel):
    """The owner's decision on a proposal."""

    proposal_id: str
    proposal_group: str
    decision: Decision
    title: str
    amount: float
    decided_at: str


class SimulatedTransaction(BaseModel):
    """What would have been executed after an approval; nothing touches a real bank."""

    id: str
    proposal_id: str
    kind: str
    description: str
    amount: float
    created_at: str


class StoredNotification(BaseModel):
    """A notification in the outbox, with its delivery status."""

    id: str
    recipient: str
    subject: str
    body: str
    status: NotificationStatus
    created_at: str


class DecisionRepository:
    """SQLite-backed store for proposal decisions, simulated transactions and the notification outbox."""

    def __init__(self, database_path: Path) -> None:
        """Create the database file and schema if they do not exist yet.

        Args:
            database_path: Location of the SQLite file.
        """
        self._database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a short-lived connection that commits on success and rolls back on error.

        Returns:
            A context manager yielding the connection.
        """
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def list_decisions(self) -> dict[str, StoredDecision]:
        """Load all decisions.

        Returns:
            Decisions keyed by proposal id.
        """
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM proposal_decisions").fetchall()
        return {row["proposal_id"]: StoredDecision(**dict(row)) for row in rows}

    def record_decision(
        self,
        decision: StoredDecision,
        transaction: SimulatedTransaction | None,
        notification: StoredNotification | None,
    ) -> None:
        """Store a decision together with its simulated transaction and notification in one transaction.

        Args:
            decision: The owner's decision.
            transaction: The simulated transaction for an approval, `None` for a decline.
            notification: The notification to enqueue, if any.
        """
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO proposal_decisions VALUES (?, ?, ?, ?, ?, ?)",
                (
                    decision.proposal_id,
                    decision.proposal_group,
                    decision.decision,
                    decision.title,
                    decision.amount,
                    decision.decided_at,
                ),
            )
            if transaction is not None:
                connection.execute(
                    "INSERT INTO simulated_transactions VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        transaction.id,
                        transaction.proposal_id,
                        transaction.kind,
                        transaction.description,
                        transaction.amount,
                        transaction.created_at,
                    ),
                )
            if notification is not None:
                connection.execute(
                    "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        notification.id,
                        notification.recipient,
                        notification.subject,
                        notification.body,
                        notification.status,
                        notification.created_at,
                    ),
                )

    def set_notification_status(self, notification_id: str, status: NotificationStatus) -> None:
        """Update the delivery status of a notification.

        Args:
            notification_id: Id of the notification.
            status: New delivery status.
        """
        with self._connect() as connection:
            connection.execute("UPDATE notifications SET status = ? WHERE id = ?", (status, notification_id))

    def list_transactions(self) -> list[SimulatedTransaction]:
        """List simulated transactions, newest first.

        Returns:
            The simulated transactions.
        """
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM simulated_transactions ORDER BY created_at DESC"
            ).fetchall()
        return [SimulatedTransaction(**dict(row)) for row in rows]

    def list_notifications(self, limit: int = 50) -> list[StoredNotification]:
        """List notifications in the outbox, newest first.

        Args:
            limit: Maximum number of notifications.

        Returns:
            The notifications.
        """
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [StoredNotification(**dict(row)) for row in rows]


def new_id() -> str:
    """Create a random id for stored records.

    Returns:
        A 32-character hex id.
    """
    return uuid.uuid4().hex


def now_iso() -> str:
    """Current UTC time for stored records.

    Returns:
        ISO-8601 timestamp with a `Z` suffix.
    """
    return _to_iso(datetime.now(UTC))


@lru_cache
def get_decision_repository() -> DecisionRepository:
    """Create the repository once per process.

    Returns:
        The shared decision repository.
    """
    return DecisionRepository(get_settings().database_path)
