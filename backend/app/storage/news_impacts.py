import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS news_impacts (
    article_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    events TEXT NOT NULL,
    rejected_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
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

    def list_impacts(self) -> list[NewsImpact]:
        """List the applied news impacts, oldest first (the order their events are sent in).

        Returns:
            The news impacts.
        """
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM news_impacts ORDER BY created_at").fetchall()
        return [NewsImpact(**{**dict(row), "events": json.loads(row["events"])}) for row in rows]

    def all_events(self) -> list[dict[str, Any]]:
        """All events of all applied news impacts, ready to send to the forecast service.

        Returns:
            The events.
        """
        return [event for impact in self.list_impacts() for event in impact.events]

    def save_impact(self, impact: NewsImpact) -> None:
        """Store or replace the impact of one article.

        Args:
            impact: The news impact.
        """
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO news_impacts VALUES (?, ?, ?, ?, ?)",
                (
                    impact.article_id,
                    impact.title,
                    json.dumps(impact.events),
                    impact.rejected_count,
                    impact.created_at,
                ),
            )

    def delete_impact(self, article_id: str) -> bool:
        """Stop taking an article into account.

        Args:
            article_id: Id of the article.

        Returns:
            `True` if an impact was removed.
        """
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM news_impacts WHERE article_id = ?", (article_id,))
        return cursor.rowcount > 0


@lru_cache
def get_news_impact_repository() -> NewsImpactRepository:
    """Create the repository once per process.

    Returns:
        The shared news impact repository.
    """
    return NewsImpactRepository(get_settings().database_path)
