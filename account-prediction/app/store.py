"""Where account data comes from.

For the demo, every account is a folder:
    {DATA_DIR}/accounts/{account_id}/statement.csv   the bank statement (organisers' format)
    {DATA_DIR}/accounts/{account_id}/profile.json    {"closing_balance": ..., "description": "..."}

closing_balance is the balance after the last booking (the statement has no balance column).
description is a one-line description of the business for the news model, e.g. "Pizzeria in Germany".

In the full solution, replace FolderStore with a class that has the same methods but reads from the bank API
or a database; nothing else in the service needs to change.
"""
import json
import re
from pathlib import Path

ACCOUNT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")   # also stops paths like "../../etc"


class AccountNotFound(KeyError):
    pass


class FolderStore:
    def __init__(self, data_dir: str):
        self.root = Path(data_dir) / "accounts"

    def _folder(self, account_id: str) -> Path:
        if not ACCOUNT_ID.match(account_id):
            raise AccountNotFound(account_id)
        return self.root / account_id

    def load(self, account_id: str) -> tuple[bytes, dict]:
        """Return (statement CSV bytes, profile dict). Raises AccountNotFound."""
        folder = self._folder(account_id)
        try:
            raw = (folder / "statement.csv").read_bytes()
            profile = json.loads((folder / "profile.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise AccountNotFound(account_id) from None
        return raw, profile

    def save(self, account_id: str, statement: bytes, closing_balance: float, description: str | None) -> None:
        """Store a statement and its closing balance; keeps an existing description unless a new one is given."""
        folder = self._folder(account_id)
        folder.mkdir(parents=True, exist_ok=True)
        profile_path = folder / "profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
        profile["closing_balance"] = closing_balance
        if description is not None:
            profile["description"] = description
        (folder / "statement.csv").write_bytes(statement)
        profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
