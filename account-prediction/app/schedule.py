"""Find scheduled payments (rent, payroll, taxes, ...) in a statement automatically.

A group of transactions counts as one scheduled payment when it
  * goes to / comes from the same counterparty, with the same transaction type and direction,
  * falls on roughly the same day of the month (within MAX_DAY_SPREAD days),
  * happens at most once per calendar month, at least MIN_OCCURRENCES times,
  * repeats every month or every 3 months without gaps,
  * has not stopped (the last payment is no older than one cycle).
Everything else (card sales, payouts, supplier invoices) is "variable cash" and is learned week by week.

Limits worth knowing: a payment whose amount or day changed fewer than MIN_OCCURRENCES months ago,
or a monthly payment that skipped a month, is treated as variable cash.
"""
from datetime import date

import numpy as np
import pandas as pd
from pydantic import BaseModel

MIN_OCCURRENCES = 3
MAX_DAY_SPREAD = 3           # days; payments a few days apart in the month are the same payment
RECENT = 3                   # day and amount are taken from the last few payments


class Payment(BaseModel):
    """One scheduled payment. 'name' is what events refer to (shift_amount.stream)."""
    name: str
    day: int                          # day of the month (moved to the month's last day if the month is shorter)
    months: list[int] | None = None   # None = every month, else e.g. [3, 6, 9, 12]
    amount: float                     # EUR per payment, negative = money out
    counterparty: str
    transaction_type: str
    last_reference: str               # helps a person (or the LLM) see what the payment is
    last_date: date


def detect_schedule(tx: pd.DataFrame) -> tuple[list[Payment], pd.Series]:
    """Return the scheduled payments and a boolean mask marking the transactions that belong to them."""
    is_scheduled = pd.Series(False, index=tx.index)
    found: list[Payment] = []
    last_month = _month_no(tx["date"].max())

    for _, group in tx.groupby(["counterparty", "type", np.sign(tx["eur"])]):
        for cluster in _split_by_day_of_month(group):
            payment = _as_payment(cluster, last_month)
            if payment is not None:
                found.append(payment)
                is_scheduled[cluster.index] = True

    return _unique_names(sorted(found, key=lambda p: (p.day, p.counterparty, p.amount))), is_scheduled


def _split_by_day_of_month(group: pd.DataFrame) -> list[pd.DataFrame]:
    """Split one counterparty's transactions into clusters of nearby days of the month (e.g. the 10th vs the 15th)."""
    g = group.assign(dom=group["date"].dt.day).sort_values("dom")
    cluster_id = (g["dom"].diff() > MAX_DAY_SPREAD).cumsum()
    return [c.drop(columns="dom").sort_values("date") for _, c in g.groupby(cluster_id)]


def _as_payment(c: pd.DataFrame, last_month: int) -> Payment | None:
    """Turn a cluster into a Payment if it is regular enough, else None."""
    months = c["date"].map(_month_no)
    if len(c) < MIN_OCCURRENCES or months.duplicated().any():
        return None                                   # too rare, or several times a month (= variable cash)

    gaps = set(np.diff(months.to_numpy()))
    if gaps == {1}:
        cycle = 1
    elif gaps == {3}:
        cycle = 3
    else:
        return None                                   # irregular
    if months.iloc[-1] < last_month - cycle:
        return None                                   # stopped

    recent, last = c.tail(RECENT), c.iloc[-1]
    return Payment(
        name=last["counterparty"],
        day=int(recent["date"].dt.day.median()),
        months=None if cycle == 1 else sorted({(last["date"].month - 1 + k) % 12 + 1 for k in (0, 3, 6, 9)}),
        amount=round(float(recent["eur"].median()), 2),
        counterparty=last["counterparty"],
        transaction_type=last["type"],
        last_reference=last["reference"],
        last_date=last["date"].date(),
    )


def _month_no(d: pd.Timestamp) -> int:
    return d.year * 12 + d.month


def _unique_names(payments: list[Payment]) -> list[Payment]:
    """Several payments to the same counterparty get '#2', '#3', ... so every name is unique."""
    seen: dict[str, int] = {}
    for p in payments:
        seen[p.name] = seen.get(p.name, 0) + 1
        if seen[p.name] > 1:
            p.name = f"{p.name} #{seen[p.name]}"
    return payments
