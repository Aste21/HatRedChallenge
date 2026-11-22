import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.accounts import AccountProfile, get_account
from app.agents.chat.charts import ChartSpec
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/dashboard-defaults", tags=["dashboard"])


class DashboardChart(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    spec: ChartSpec
    span: Literal[4, 6, 8, 12]


class DashboardDefaults(BaseModel):
    charts: list[DashboardChart] = Field(default_factory=list, max_length=24)


@contextmanager
def defaults_connection(settings: Settings) -> Iterator[sqlite3.Connection]:
    """Open the backend database and initialize the account defaults table."""
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(settings.database_path)) as connection, connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_defaults (
                account_id TEXT PRIMARY KEY,
                layout TEXT NOT NULL
            )
        """)
        yield connection


@router.get("", response_model=DashboardDefaults)
def get_defaults(
    account: Annotated[AccountProfile, Depends(get_account)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DashboardDefaults:
    """Read the default chart layout for the signed-in account."""
    with defaults_connection(settings) as connection:
        saved = connection.execute(
            "SELECT layout FROM dashboard_defaults WHERE account_id = ?", (account.id,)
        ).fetchone()
    return DashboardDefaults.model_validate_json(saved[0]) if saved else DashboardDefaults()


@router.put("", status_code=204)
def initialize_defaults(
    defaults: DashboardDefaults,
    account: Annotated[AccountProfile, Depends(get_account)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Import the first nonempty layout without overwriting an existing default."""
    if defaults.charts:
        with defaults_connection(settings) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO dashboard_defaults (account_id, layout) VALUES (?, ?)",
                (account.id, defaults.model_dump_json()),
            )


@router.post("", status_code=204)
def save_defaults(
    defaults: DashboardDefaults,
    account: Annotated[AccountProfile, Depends(get_account)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Publish the edited chart layout as the account default."""
    with defaults_connection(settings) as connection:
        connection.execute(
            """
            INSERT INTO dashboard_defaults (account_id, layout) VALUES (?, ?)
            ON CONFLICT(account_id) DO UPDATE SET layout = excluded.layout
            """,
            (account.id, defaults.model_dump_json()),
        )
