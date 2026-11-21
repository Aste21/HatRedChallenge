import argparse
import json
import logging
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from html import escape
from pathlib import Path

import httpx

from app.accounts import ACCOUNTS
from app.config import get_settings
from app.notifications.email import send_email, smtp_configured


HORIZON = 90


@dataclass(frozen=True)
class Notice:
    kind: str
    subject: str
    title: str
    amount: str
    caption: str
    detail: str
    action: str


def euro(value):
    return f"{'−' if value < 0 else ''}€{abs(value):,.2f}"


def long_date(iso):
    return date.fromisoformat(iso).strftime("%d %B %Y")


def balance_notice(amount, day):
    return Notice(
        "balance",
        f"Balance alert | {euro(amount)}",
        "Your account closed below zero",
        euro(amount),
        f"Closing balance on {long_date(day)}",
        "Review your latest transactions and upcoming payments to see what is due next.",
        "Dashboard  →  Cashflow",
    )


def forecast_notice(day, estimate, current):
    return Notice(
        "forecast",
        f"Cashflow forecast | Shortfall on {long_date(day)}",
        "A cash shortfall is forecast",
        euro(estimate),
        f"Projected balance on {long_date(day)}",
        f"Your latest closing balance is {euro(current)}. This is the first day in the "
        "next 90 days when the median forecast falls below zero.",
        "Dashboard  →  Forecast",
    )


def investment_notice(amount, days):
    return Notice(
        "investment",
        f"Deposit proposal | {euro(amount)} for {days} days",
        "You have cash to set aside",
        euro(amount),
        f"Available for a {days}-day deposit",
        f"Your 90-day forecast leaves room for this {days}-day deposit while keeping "
        "your estimated cash buffer. Review the terms in your dashboard before you decide.",
        "Dashboard  →  Proposals",
    )


def deliver(settings, account, notice):
    styles = {
        "balance": ("Account alert", "#923c37", "#faeeeb"),
        "forecast": ("Cashflow outlook", "#77511c", "#faf2df"),
        "investment": ("Investment proposal", "#145e4d", "#e9f4ed"),
    }
    section, accent, tint = styles[notice.kind]
    business = ACCOUNTS[account].business_name

    text = (
        f"{business} | {section}\n\n"
        f"{notice.title}\n{notice.amount}\n{notice.caption}\n\n"
        f"{notice.detail}\n\n{notice.action}"
    )

    html = f"""<!doctype html>
<html lang="en">
<body style="margin:0;background:#edf1ee;font-family:Arial,Helvetica,sans-serif;color:#18312b">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#edf1ee">
    <tr>
      <td align="center" style="padding:24px 12px">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#ffffff"
               style="max-width:540px;border:1px solid #d7e0d9;border-radius:12px">
          <tr>
            <td bgcolor="#193b32" style="padding:18px 24px;border-radius:12px 12px 0 0">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="color:#ffffff;font-size:17px;font-weight:bold">
                    {escape(business)}
                  </td>
                  <td align="right" style="color:#d5e7df;font-size:13px">
                    {section}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:24px">
              <h1 style="margin:0 0 18px;font:normal 29px/1.2 Georgia,serif;color:#18312b">
                {escape(notice.title)}
              </h1>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td bgcolor="{tint}" style="padding:18px 20px;border-left:4px solid {accent}">
                    <div style="color:{accent};font-size:36px;line-height:1.25;font-weight:bold">
                      {escape(notice.amount)}
                    </div>
                    <div style="margin-top:5px;color:#475951;font-size:14px">
                      {escape(notice.caption)}
                    </div>
                  </td>
                </tr>
              </table>
              <p style="margin:18px 0 21px;font-size:16px;line-height:1.55;color:#364b43">
                {escape(notice.detail)}
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td bgcolor="{accent}"
                      style="padding:11px 16px;border-radius:6px;color:white;font-size:14px;font-weight:bold">
                    {escape(notice.action)}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    send_email(settings, settings.owner_email, notice.subject, text, html=html)


def send_once(db, settings, account, as_of, key, notice):
    with db:
        db.execute("BEGIN IMMEDIATE")
        latest = db.execute(
            "SELECT booked_on FROM balance_alerts WHERE account = ?",
            (account,),
        ).fetchone()

        if latest and latest[0] > as_of:
            return

        inserted = db.execute(
            "INSERT OR IGNORE INTO sent_notices VALUES (?, ?)",
            (account, key),
        )
        if inserted.rowcount == 1:
            deliver(settings, account, notice)


def check_balance(settings, api, db, account):
    headers = {"X-Account-Id": account}
    response = httpx.get(
        f"{api}/api/forecast",
        params={"horizon": HORIZON},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    forecast = response.json()

    if forecast["account_id"] != account:
        raise ValueError("Unexpected account in forecast")

    day = date.fromisoformat(forecast["as_of"])
    as_of = day.isoformat()
    current = Decimal(str(forecast["start_balance"]))

    if not current.is_finite():
        raise ValueError("Invalid closing balance")

    with db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute(
            "SELECT booked_on, alerted FROM balance_alerts WHERE account = ?",
            (account,),
        ).fetchone()

        if previous and previous[0] > as_of:
            return

        if current < 0 and not (previous and previous[1]):
            deliver(settings, account, balance_notice(current, as_of))

        db.execute(
            "INSERT OR REPLACE INTO balance_alerts VALUES (?, ?, ?)",
            (account, as_of, int(current < 0)),
        )

    logging.info("Checked %s: EUR %.2f on %s", account, current, as_of)

    official = forecast["official"]
    end = (day + timedelta(days=HORIZON)).isoformat()

    first_low = min(
        (
            row for row in official["daily"]
            if as_of < row["date"] <= end and row["p50"] < 0
        ),
        key=lambda row: row["date"],
        default=None,
    )

    if current >= 0 and first_low:
        low_day = first_low["date"]
        notice = forecast_notice(low_day, first_low["p50"], current)
        send_once(db, settings, account, as_of, f"forecast:{low_day}", notice)

    limits = {
        row["days"]: row["amount"]
        for row in official["safe_to_lock"]
        if 0 < row["days"] <= HORIZON and row["amount"] > 0
    }
    if current <= 0 or not limits:
        return

    response = httpx.get(f"{api}/api/proposals", headers=headers, timeout=150)
    response.raise_for_status()
    board = response.json()

    if board["as_of"] != as_of or board["start_balance"] != forecast["start_balance"]:
        return

    offers = [
        item for item in board["proposals"]
        if item["kind"] == "fixed_term_deposit"
        and item["status"] == "awaiting_approval"
        and 0 < item["amount"] <= limits.get(item["term_days"], 0)
    ]

    if offers:
        offer = max(offers, key=lambda item: item["amount"])
        notice = investment_notice(offer["amount"], offer["term_days"])
        send_once(db, settings, account, as_of, f"investment:{as_of}", notice)


def sample_notice(kind):
    if kind == "forecast":
        return forecast_notice("2025-06-01", -1704.17, 2006.31)

    if kind == "investment":
        return investment_notice(5000, 30)

    root = Path(__file__).resolve().parents[3]
    statement = root / "frontend/src/lib/server/statements/amalfi.json"
    history = json.loads(statement.read_text(encoding="utf-8"))["history"]
    lowest = min(history, key=lambda row: row["balance"])

    if lowest["balance"] >= 0:
        raise ValueError("No negative closing balance in the sample statement")

    return balance_notice(Decimal(lowest["balance"]) / 100, lowest["date"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument(
        "--demo",
        nargs="?",
        const="balance",
        choices=("balance", "forecast", "investment", "all"),
    )
    args = parser.parse_args()

    if args.interval < 1:
        parser.error("--interval must be at least 1 second")

    settings = get_settings()
    if not smtp_configured(settings) or not settings.smtp_password:
        parser.error("Set OWNER_EMAIL, SMTP_HOST, SMTP_USER and SMTP_PASSWORD in backend/.env")

    if args.demo:
        kinds = ("balance", "forecast", "investment") if args.demo == "all" else (args.demo,)
        for kind in kinds:
            deliver(settings, "amalfi", sample_notice(kind))
            print(f"SMTP accepted the {kind} message.")
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    path = settings.database_path.with_name("balance-alerts.sqlite3")
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path, timeout=30)) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS balance_alerts
                (account TEXT PRIMARY KEY, booked_on TEXT NOT NULL, alerted INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS sent_notices
                (account TEXT, notice_key TEXT, PRIMARY KEY (account, notice_key));
        """)

        while True:
            for account in ACCOUNTS:
                try:
                    check_balance(settings, args.api_url.rstrip("/"), db, account)
                except (httpx.HTTPError, OSError, sqlite3.Error, KeyError, ValueError, ArithmeticError):
                    logging.exception("Balance check failed for %s", account)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()