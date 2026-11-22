import argparse
import asyncio
import json
import logging
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any, Literal

import httpx

from app.accounts import ACCOUNTS
from app.config import Settings, get_settings
from app.notifications.email import send_email, smtp_configured

FORECAST_HORIZON_DAYS = 90
PLACEMENT_KINDS = ("fixed_term_deposit", "fixed_term_investment")

NoticeKind = Literal["balance", "forecast", "investment"]

NOTICE_STYLES: dict[NoticeKind, tuple[str, str, str]] = {
    "balance": ("Account alert", "#923c37", "#faeeeb"),
    "forecast": ("Cashflow outlook", "#77511c", "#faf2df"),
    "investment": ("Investment proposal", "#145e4d", "#e9f4ed"),
}


@dataclass(frozen=True)
class Notice:
    """One e-mail to the owner: headline amount, explanation and where to look in the app."""

    kind: NoticeKind
    subject: str
    title: str
    amount: str
    caption: str
    detail: str
    action: str


def format_euro(amount: Decimal | float) -> str:
    """Format an amount as euros for e-mail texts.

    Args:
        amount: Amount in EUR.

    Returns:
        The formatted amount, e.g. `€7,391.53` or `−€1,200.00`.
    """
    sign = "−" if amount < 0 else ""
    return f"{sign}€{abs(amount):,.2f}"


def format_long_date(iso_date: str) -> str:
    """Format an ISO calendar date for e-mail texts.

    Args:
        iso_date: Date as `YYYY-MM-DD`.

    Returns:
        The date, e.g. `03 July 2025`.
    """
    return date.fromisoformat(iso_date).strftime("%d %B %Y")


def balance_notice(closing_balance: Decimal, booked_on: str) -> Notice:
    """Build the alert for an account that closed the day below zero.

    Args:
        closing_balance: The negative closing balance in EUR.
        booked_on: ISO date of that closing balance.

    Returns:
        The notice.
    """
    return Notice(
        kind="balance",
        subject=f"Balance alert | {format_euro(closing_balance)}",
        title="Your account closed below zero",
        amount=format_euro(closing_balance),
        caption=f"Closing balance on {format_long_date(booked_on)}",
        detail="Review your latest transactions and upcoming payments to see what is due next.",
        action="Dashboard  →  Cashflow",
    )


def forecast_notice(shortfall_date: str, projected_balance: float, current_balance: Decimal) -> Notice:
    """Build the warning for the first forecast day with a negative median balance.

    Args:
        shortfall_date: ISO date of the first day below zero.
        projected_balance: Median (p50) forecast balance on that day in EUR.
        current_balance: The latest closing balance in EUR.

    Returns:
        The notice.
    """
    return Notice(
        kind="forecast",
        subject=f"Cashflow forecast | Shortfall on {format_long_date(shortfall_date)}",
        title="A cash shortfall is forecast",
        amount=format_euro(projected_balance),
        caption=f"Projected balance on {format_long_date(shortfall_date)}",
        detail=(
            f"Your latest closing balance is {format_euro(current_balance)}. This is the first day in the "
            f"next {FORECAST_HORIZON_DAYS} days when the median forecast falls below zero."
        ),
        action="Dashboard  →  Forecast",
    )


def investment_notice(amount: float, term_days: int) -> Notice:
    """Build the hint that the forecast leaves cash for a fixed-term placement.

    Args:
        amount: Amount of the proposed placement in EUR.
        term_days: Term of the placement in days.

    Returns:
        The notice.
    """
    return Notice(
        kind="investment",
        subject=f"Investment proposal | {format_euro(amount)} for {term_days} days",
        title="You have cash to set aside",
        amount=format_euro(amount),
        caption=f"Available for a {term_days}-day placement",
        detail=(
            f"Your {FORECAST_HORIZON_DAYS}-day forecast leaves room for this {term_days}-day placement while "
            "keeping your estimated cash buffer. Review the terms in your dashboard before you decide."
        ),
        action="Dashboard  →  Proposals",
    )


def deliver(settings: Settings, account_id: str, notice: Notice) -> None:
    """Send a notice to the owner as plain text and HTML e-mail.

    Args:
        settings: Application settings with the SMTP configuration and owner address.
        account_id: Account the notice is about (its business name heads the e-mail).
        notice: The notice to send.
    """
    section, accent, tint = NOTICE_STYLES[notice.kind]
    business = ACCOUNTS[account_id].business_name

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


def send_once(
    database: sqlite3.Connection,
    settings: Settings,
    account_id: str,
    as_of: str,
    notice_key: str,
    notice: Notice,
) -> None:
    """Send a notice unless the same key was already sent or a newer statement was checked meanwhile.

    Args:
        database: Connection to the alerts database.
        settings: Application settings with the SMTP configuration.
        account_id: Account the notice is about.
        as_of: ISO date of the statement the notice is based on.
        notice_key: Deduplication key, e.g. `forecast:2025-06-01`.
        notice: The notice to send.

    Steps:
        1. Lock the database so parallel checkers cannot both send.
        2. Skip the notice if a newer statement date was already recorded for the account.
        3. Record the key and deliver; a failed delivery rolls the record back so the next run retries.
    """
    with database:
        database.execute("BEGIN IMMEDIATE")
        latest = database.execute(
            "SELECT booked_on FROM balance_alerts WHERE account = ?",
            (account_id,),
        ).fetchone()
        if latest and latest[0] > as_of:
            return

        inserted = database.execute(
            "INSERT OR IGNORE INTO sent_notices VALUES (?, ?)",
            (account_id, notice_key),
        )
        if inserted.rowcount == 1:
            deliver(settings, account_id, notice)


def _best_placement(proposals: list[dict[str, Any]], limits: dict[int, float]) -> dict[str, Any] | None:
    """Pick the placement to mention: the agent's top recommendation, else the largest open offer.

    Args:
        proposals: Proposals from `GET /api/proposals`.
        limits: Positive safe-to-lock amounts by term in days.

    Returns:
        The chosen proposal, or `None` if no open placement fits the forecast limits.
    """
    open_placements = [
        proposal
        for proposal in proposals
        if proposal["kind"] in PLACEMENT_KINDS
        and proposal["status"] == "awaiting_approval"
        and 0
        < proposal["amount"]
        <= limits.get(proposal.get("forecast_limit_days") or proposal["term_days"], 0)
    ]
    if not open_placements:
        return None
    top_recommendation = next(
        (
            proposal
            for proposal in open_placements
            if proposal.get("family_rank") == 1 and proposal.get("is_recommended_term")
        ),
        None,
    )
    return top_recommendation or max(open_placements, key=lambda proposal: proposal["amount"])


def check_balance(
    settings: Settings,
    api_url: str,
    database: sqlite3.Connection,
    account_id: str,
    *,
    investment_only: bool = False,
) -> None:
    """Check one account and send the balance, shortfall and investment notices that are due.

    Args:
        settings: Application settings with the SMTP configuration.
        api_url: Base URL of the backend, without a trailing slash.
        database: Connection to the alerts database.
        account_id: Account to check (sent as `X-Account-Id`).
        investment_only: Limit delivery to investment opportunities.

    Steps:
        1. Fetch the forecast and validate the account and closing balance.
        2. Alert once when the account closes below zero; reset when it is positive again.
        3. Warn once per shortfall date when the median forecast first drops below zero.
        4. If the forecast leaves cash to lock, fetch the proposals board and mention the best open
           placement once per statement date.
    """
    headers = {"X-Account-Id": account_id}
    response = httpx.get(
        f"{api_url}/api/forecast",
        params={"horizon": FORECAST_HORIZON_DAYS},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    forecast = response.json()
    if forecast["account_id"] != account_id:
        raise ValueError("Unexpected account in forecast")

    statement_date = date.fromisoformat(forecast["as_of"])
    as_of = statement_date.isoformat()
    current_balance = Decimal(str(forecast["start_balance"]))
    if not current_balance.is_finite():
        raise ValueError("Invalid closing balance")

    with database:
        database.execute("BEGIN IMMEDIATE")
        previous = database.execute(
            "SELECT booked_on, alerted FROM balance_alerts WHERE account = ?",
            (account_id,),
        ).fetchone()
        if previous and previous[0] > as_of:
            return
        if not investment_only and current_balance < 0 and not (previous and previous[1]):
            deliver(settings, account_id, balance_notice(current_balance, as_of))
        alerted = current_balance < 0 and (not investment_only or bool(previous and previous[1]))
        database.execute(
            "INSERT OR REPLACE INTO balance_alerts VALUES (?, ?, ?)",
            (account_id, as_of, int(alerted)),
        )
    logging.info("Checked %s: EUR %.2f on %s", account_id, current_balance, as_of)

    official = forecast["official"]
    horizon_end = (statement_date + timedelta(days=FORECAST_HORIZON_DAYS)).isoformat()
    first_shortfall = min(
        (band for band in official["daily"] if as_of < band["date"] <= horizon_end and band["p50"] < 0),
        key=lambda band: band["date"],
        default=None,
    )
    if not investment_only and current_balance >= 0 and first_shortfall:
        shortfall_date = first_shortfall["date"]
        notice = forecast_notice(shortfall_date, first_shortfall["p50"], current_balance)
        send_once(database, settings, account_id, as_of, f"forecast:{shortfall_date}", notice)

    limits = {
        limit["days"]: limit["amount"]
        for limit in official["safe_to_lock"]
        if 0 < limit["days"] <= FORECAST_HORIZON_DAYS and limit["amount"] > 0
    }
    if current_balance <= 0 or not limits:
        return

    response = httpx.get(f"{api_url}/api/proposals", headers=headers, timeout=150)
    response.raise_for_status()
    board = response.json()
    if board["as_of"] != as_of or board["start_balance"] != forecast["start_balance"]:
        return

    placement = _best_placement(board["proposals"], limits)
    if placement is not None:
        notice = investment_notice(placement["amount"], placement["term_days"])
        send_once(database, settings, account_id, as_of, f"investment:{as_of}", notice)


def sample_notice(kind: NoticeKind) -> Notice:
    """Build a demo notice from the Amalfi sample data.

    Args:
        kind: Which notice to build.

    Returns:
        The notice.
    """
    if kind == "forecast":
        return forecast_notice("2025-06-01", -1704.17, Decimal("2006.31"))
    if kind == "investment":
        return investment_notice(5000, 30)

    root = Path(__file__).resolve().parents[3]
    statement_path = root / "frontend/src/lib/server/statements/amalfi.json"
    history = json.loads(statement_path.read_text(encoding="utf-8"))["history"]
    lowest = min(history, key=lambda row: row["balance"])
    if lowest["balance"] >= 0:
        raise ValueError("No negative closing balance in the sample statement")
    return balance_notice(Decimal(lowest["balance"]) / 100, lowest["date"])


def check_accounts(settings: Settings, api_url: str, *, investment_only: bool = False) -> None:
    """Check all accounts and persist the delivery keys beside the backend database.

    Args:
        settings: Application settings with storage and SMTP configuration.
        api_url: Backend API base URL.
        investment_only: Limit delivery to investment opportunities.

    Steps:
        1. Open the alerts database and initialize its tables.
        2. Check each account independently.
    """
    database_path = settings.database_path.with_name("balance-alerts.sqlite3")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path, timeout=30)) as database:
        database.executescript("""
            CREATE TABLE IF NOT EXISTS balance_alerts
                (account TEXT PRIMARY KEY, booked_on TEXT NOT NULL, alerted INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS sent_notices
                (account TEXT, notice_key TEXT, PRIMARY KEY (account, notice_key));
        """)
        for account_id in ACCOUNTS:
            try:
                check_balance(
                    settings, api_url.rstrip("/"), database, account_id, investment_only=investment_only
                )
            except (httpx.HTTPError, OSError, sqlite3.Error, KeyError, ValueError, ArithmeticError):
                logging.exception("Balance check failed for %s", account_id)


async def monitor_investments(settings: Settings) -> None:
    """Run the investment check every five minutes during the backend's lifetime.

    Args:
        settings: Application settings with the backend URL and SMTP configuration.

    Steps:
        1. Allow the backend to start accepting HTTP requests.
        2. Check for investment opportunities off the event loop and log storage failures.
        3. Wait five minutes before checking again.
    """
    await asyncio.sleep(5)
    while True:
        try:
            await asyncio.to_thread(
                check_accounts, settings, settings.investment_alert_api_url, investment_only=True
            )
        except (OSError, sqlite3.Error):
            logging.exception("Investment alert storage is unavailable")
        await asyncio.sleep(300)


def main() -> None:
    """Run the alert checker, or send demo e-mails with `--demo`.

    Steps:
        1. Parse the arguments and require SMTP settings.
        2. With `--demo`, send the requested sample notices once and exit.
        3. Otherwise open the alerts database and check every account each interval.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between checks")
    parser.add_argument(
        "--demo",
        nargs="?",
        const="balance",
        choices=("balance", "forecast", "investment", "all"),
        help="Send sample notices and exit",
    )
    arguments = parser.parse_args()
    if arguments.interval < 1:
        parser.error("--interval must be at least 1 second")

    settings = get_settings()
    if not smtp_configured(settings) or not settings.smtp_password:
        parser.error("Set OWNER_EMAIL, SMTP_HOST, SMTP_USER and SMTP_PASSWORD in backend/.env")

    if arguments.demo:
        kinds: tuple[NoticeKind, ...] = (
            ("balance", "forecast", "investment") if arguments.demo == "all" else (arguments.demo,)
        )
        for kind in kinds:
            notice = sample_notice(kind)
            if kind == "investment":
                notice = replace(notice, subject=f"[Demo] {notice.subject}")
            deliver(settings, "amalfi", notice)
            print(f"SMTP accepted the {kind} message.")
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    while True:
        check_accounts(settings, arguments.api_url)
        time.sleep(arguments.interval)


if __name__ == "__main__":
    main()
