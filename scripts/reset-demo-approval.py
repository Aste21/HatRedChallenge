"""Reset one approved Amalfi demo proposal inside the running OpenShift backend."""

import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile


def reset_approval(path: Path, proposal_id: str | None, preview: bool) -> None:
    """Reopen one approved demo decision and save its related rows before removal.

    Args:
        path: Existing demo SQLite database.
        proposal_id: Exact ID when selecting among multiple approvals.
        preview: List matching approvals using a read-only connection.

    Steps:
        1. Select the requested approval for Amalfi in a consistent transaction.
        2. Save just that decision, its simulated transaction and its notification to the PVC.
        3. Remove the selected rows in one commit.
    """
    mode = "ro" if preview else "rw"
    with closing(sqlite3.connect(f"{path.as_uri()}?mode={mode}", uri=True, timeout=10)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN" if preview else "BEGIN IMMEDIATE")
        decisions = db.execute(
            "SELECT * FROM proposal_decisions WHERE account_id='amalfi' AND decision='approved' "
            "AND (? IS NULL OR proposal_id=?) ORDER BY decided_at DESC",
            (proposal_id, proposal_id),
        ).fetchall()
        if not decisions:
            print("No matching approval to reset for Amalfi.")
            return
        for row in decisions:
            print(f"{row['proposal_id']}  {row['decided_at']}  {row['title']}")
        if preview:
            return
        if len(decisions) > 1:
            raise SystemExit("Multiple approvals found. Run again with -ProposalId and one ID listed above.")

        decision = decisions[0]
        transactions = db.execute(
            "SELECT * FROM simulated_transactions WHERE account_id='amalfi' AND proposal_id=?",
            (decision["proposal_id"],),
        ).fetchall()
        notices = db.execute(
            "SELECT * FROM notifications WHERE account_id='amalfi' AND created_at=? AND subject=?",
            (decision["decided_at"], f"Approved (simulated): {decision['title']}"),
        ).fetchall()
        if len(notices) > 1:
            raise SystemExit("Multiple matching notifications found. Review them before resetting.")
        snapshot = {
            "proposal_decisions": [dict(decision)],
            "simulated_transactions": [dict(row) for row in transactions],
            "notifications": [dict(row) for row in notices],
        }
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix="amalfi-approval-", suffix=".json", delete=False
        ) as backup:
            json.dump(snapshot, backup, indent=2, ensure_ascii=False)
            backup.flush()
            os.fsync(backup.fileno())
        db.executemany("DELETE FROM notifications WHERE id=?", [(row["id"],) for row in notices])
        db.execute(
            "DELETE FROM simulated_transactions WHERE account_id='amalfi' AND proposal_id=?",
            (decision["proposal_id"],),
        )
        db.execute(
            "DELETE FROM proposal_decisions WHERE account_id='amalfi' AND proposal_id=?",
            (decision["proposal_id"],),
        )
    print(f"Approval reset. Backup: {backup.name}")


if __name__ == "__main__":
    path = Path("/data/cfocus-demo.sqlite3")
    if Path(os.environ["DATABASE_PATH"]).resolve() != path:
        raise SystemExit("The backend is not using the expected CFOcus demo database.")
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in ("preview", "reset"):
        raise SystemExit("Usage: reset-demo-approval.py {preview|reset} [proposal-id]")
    reset_approval(path, sys.argv[2] if len(sys.argv) == 3 else None, sys.argv[1] == "preview")
