"""Read a bank statement CSV into a clean table of transactions in EUR.

Expected format (the organisers' export): semicolon-separated, decimal comma, dates as dd.mm.yy, columns
"Booking Date", "Transaction Type", "Payment Reference", "Beneficiary/Payer", "Amount", "Currency".
Foreign-currency rows must state the rate in the reference, e.g. "(4166.67 CHF @ 1.047 EUR/CHF)".
To support another bank's export, change COLUMNS / read_statement only; the rest of the service uses the clean table.
"""
import io
import re

import pandas as pd

COLUMNS = {   # bank export column -> name used in the service
    "Booking Date": "date",
    "Transaction Type": "type",
    "Payment Reference": "reference",
    "Beneficiary/Payer": "counterparty",
    "Amount": "amount",
    "Currency": "currency",
}


class StatementError(ValueError):
    """The file cannot be read as a bank statement. The message is safe to show to the user."""


def read_statement(raw: bytes) -> pd.DataFrame:
    """CSV bytes -> DataFrame with columns date, type, reference, counterparty, amount, currency, eur.

    'eur' is the amount converted to EUR (negative = money out). Rows are sorted by date.
    """
    try:
        df = pd.read_csv(io.BytesIO(raw), sep=";", decimal=",", dtype=str, keep_default_na=False)
    except Exception as exc:
        raise StatementError(f"not a readable CSV file: {exc}") from exc

    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise StatementError(f"missing columns: {missing}")
    df = df[list(COLUMNS)].rename(columns=COLUMNS)
    if df.empty:
        raise StatementError("the statement has no transactions")

    try:
        df["date"] = pd.to_datetime(df["date"], format="%d.%m.%y")
        df["amount"] = df["amount"].str.replace(",", ".", regex=False).astype(float)
    except Exception as exc:
        raise StatementError(f"unreadable date or amount: {exc}") from exc

    df["eur"] = [_to_eur(r.amount, r.currency, r.reference) for r in df.itertuples()]
    return df.sort_values("date", kind="stable").reset_index(drop=True)


def _to_eur(amount: float, currency: str, reference: str) -> float:
    """Convert one amount to EUR, using the rate written in the payment reference for foreign currencies."""
    if currency == "EUR":
        return amount
    m = re.search(rf"@ ([\d.]+) EUR/{re.escape(currency)}", reference)
    if not m:
        raise StatementError(f"no EUR/{currency} rate in the reference of a {currency} payment: {reference!r}")
    return amount * float(m.group(1))
