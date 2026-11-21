import argparse
import json
import logging
import sqlite3
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx

from app.config import Settings, get_settings
from app.notifications.email import send_email, smtp_configured


def send_alert(settings: Settings, balance: Decimal, booked_on: date, demo: bool = False) -> None:
    amount = f"−€{abs(balance):,.2f}"
    day = booked_on.strftime("%d %B %Y")
    subject = f"Balance alert | {amount}"
    if demo:
        subject = f"[Demo] {subject}"

    body = (
        f"Your account closed below zero on {day}.\n\n"
        f"Closing balance: {amount}\n\n"
        "Open Cashflow to review your balance and upcoming payments."
    )
    html = f"""
    <div style="max-width:520px;margin:24px auto;font:16px Arial,sans-serif;color:#20332e">
      <p style="color:#526660">Cashflow · Balance alert</p>
      <h2>Your account closed below zero</h2>
      <div style="padding:20px;background:#fff3ef;border-left:4px solid #b43b21">
        <div>Closing balance · {day}</div>
        <strong style="font-size:32px;color:#982e19">{amount}</strong>
      </div>
      <p>Open Cashflow to review your balance and upcoming payments.</p>
    </div>
    """
    send_email(settings, settings.owner_email, subject, body, html=html)


def check_balance(settings: Settings, api_url: str, database: sqlite3.Connection) -> None:
    response = httpx.get(f"{api_url.rstrip('/')}/api/forecast", params={"horizon": 90}, timeout=30)
    response.raise_for_status()
    forecast = response.json()
    account = forecast["account_id"]
    booked_on = date.fromisoformat(forecast["as_of"])
    balance = Decimal(str(forecast["start_balance"]))
    if not balance.is_finite():
        raise ValueError("Invalid account balance")

    with database:
        database.execute("BEGIN IMMEDIATE")
        previous = database.execute(
            "SELECT booked_on, alerted FROM balance_alerts WHERE account = ?", (account,)
        ).fetchone()
        if previous and booked_on.isoformat() < previous[0]:
            return
        if balance < 0 and not (previous and previous[1]):
            send_alert(settings, balance, booked_on)
        database.execute(
            "INSERT OR REPLACE INTO balance_alerts VALUES (?, ?, ?)",
            (account, booked_on.isoformat(), int(balance < 0)),
        )
    logging.info("Checked %s: EUR %.2f on %s", account, balance, booked_on)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between checks")
    parser.add_argument("--demo", action="store_true", help="Send one historical example and exit")
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("--interval must be at least 1 second")

    settings = get_settings()
    if not smtp_configured(settings) or not settings.smtp_password:
        parser.exit(1, "Fill in OWNER_EMAIL and the SMTP settings in backend/.env first.\n")

    if args.demo:
        root = Path(__file__).resolve().parents[3]
        statement = json.loads((root / "frontend/src/lib/statement.json").read_text(encoding="utf-8"))
        lowest = min(statement["history"], key=lambda row: row["balance"])
        balance = Decimal(lowest["balance"]) / 100
        if balance >= 0:
            parser.exit(1, "The demo statement contains no negative closing balance.\n")
        send_alert(settings, balance, date.fromisoformat(lowest["date"]), demo=True)
        print("Demo alert accepted by the SMTP server.")
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    path = settings.database_path.with_name("balance-alerts.sqlite3")
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path, timeout=30)
    try:
        database.execute(
            "CREATE TABLE IF NOT EXISTS balance_alerts "
            "(account TEXT PRIMARY KEY, booked_on TEXT NOT NULL, alerted INTEGER NOT NULL)"
        )
        while True:
            try:
                check_balance(settings, args.api_url, database)
            except (httpx.HTTPError, OSError, sqlite3.Error, KeyError, ValueError, ArithmeticError):
                logging.exception("Balance check failed")
            time.sleep(args.interval)
    finally:
        database.close()


if __name__ == "__main__":
    main()