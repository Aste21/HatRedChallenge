import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.config import get_settings
from app.storage.schema import LEGACY_ACCOUNT_ID

SCHEMA = """
CREATE TABLE IF NOT EXISTS account_news_impacts (
    account_id TEXT NOT NULL,
    article_id TEXT NOT NULL,
    title TEXT NOT NULL,
    events TEXT NOT NULL,
    rejected_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (account_id, article_id)
);
"""


class NewsImpact(BaseModel):
    """Forecast events the forecast service derived from one article, applied at the owner's request.

    `events` are kept exactly as the forecast service returned them, so they can be sent back to
    `/forecast` unchanged.
    """

    article_id: str
    title: str
    events: list[dict[str, Any]]
    rejected_count: int
    created_at: str


class NewsImpactRepository:
    """SQLite-backed store for the news impacts the forecast takes into account."""

    def __init__(self, database_path: Path) -> None:
        """Create the database file and schema if they do not exist yet.

        Args:
            database_path: Location of the SQLite file.
        """
        self._database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            # Impacts stored before accounts existed belong to the original demo business.
            legacy = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'news_impacts'"
            ).fetchone()
            if legacy is not None:
                connection.execute(
                    "INSERT OR IGNORE INTO account_news_impacts SELECT ?, article_id, title, events, "
                    "rejected_count, created_at FROM news_impacts",
                    (LEGACY_ACCOUNT_ID,),
                )
                connection.execute("DROP TABLE news_impacts")

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

    def list_impacts(self, account_id: str) -> list[NewsImpact]:
        """List the account's applied news impacts, oldest first (the order their events are sent in).

        Args:
            account_id: The signed-in account.

        Returns:
            The news impacts.
        """
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT article_id, title, events, rejected_count, created_at FROM account_news_impacts "
                "WHERE account_id = ? ORDER BY created_at",
                (account_id,),
            ).fetchall()
        return [NewsImpact(**{**dict(row), "events": json.loads(row["events"])}) for row in rows]

    def all_events(self, account_id: str) -> list[dict[str, Any]]:
        """All events of the account's applied news impacts, ready to send to the forecast service.

        Args:
            account_id: The signed-in account.

        Returns:
            The events.
        """
        return [event for impact in self.list_impacts(account_id) for event in impact.events]

    def save_impact(self, account_id: str, impact: NewsImpact) -> None:
        """Store or replace the impact of one article for the account.

        Args:
            account_id: The signed-in account.
            impact: The news impact.
        """
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO account_news_impacts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    account_id,
                    impact.article_id,
                    impact.title,
                    json.dumps(impact.events),
                    impact.rejected_count,
                    impact.created_at,
                ),
            )

    def delete_impact(self, account_id: str, article_id: str) -> bool:
        """Stop taking an article into account for the account.

        Args:
            account_id: The signed-in account.
            article_id: Id of the article.

        Returns:
            `True` if an impact was removed.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM account_news_impacts WHERE account_id = ? AND article_id = ?",
                (account_id, article_id),
            )
        return cursor.rowcount > 0


@lru_cache
def get_news_impact_repository() -> NewsImpactRepository:
    """Create the repository once per process.

    Returns:
        The shared news impact repository.
    """
    return NewsImpactRepository(get_settings().database_path)
