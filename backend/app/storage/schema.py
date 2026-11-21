import sqlite3

# Rows stored before accounts existed all belong to the original demo business.
LEGACY_ACCOUNT_ID = "amalfi"


def add_account_column(connection: sqlite3.Connection, table: str) -> None:
    """Add the `account_id` column to a table created before accounts existed.

    Args:
        connection: Open SQLite connection.
        table: Table name (a constant from the repository's schema, never user input).
    """
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if "account_id" in columns:
        return
    try:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN account_id TEXT NOT NULL DEFAULT '{LEGACY_ACCOUNT_ID}'"
        )
    except sqlite3.OperationalError as error:
        # Two first requests can migrate at the same time; the second one finds the column already added.
        if "duplicate column" not in str(error):
            raise
