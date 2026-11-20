"""Balance forecast by simulation, and the amount that can safely be locked away.

How it works:
  1. Scheduled payments (see schedule.py) are placed on their future dates, changed by any shift_amount events.
  2. Variable cash is learned from the last N_WEEKS normal Mon-Sun weeks: each simulated future is built by
     drawing whole weeks of history at random (sales and costs from the same week, aligned by weekday).
  3. scale / closure / one_off events change the simulated variable cash.
  4. N_SIMS futures give the median and the 5-95 % band of the balance for every day.

Nothing is stored or trained ahead: the history is read on every request and the simulation takes milliseconds.
The random draws depend only on SEED, so two scenarios differ only because of their events, not by chance.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pydantic import BaseModel

from .events import Closure, Event, OneOff, Scale, ShiftAmount
from .schedule import Payment

N_WEEKS = 12              # recent normal weeks to learn variable cash from
MIN_WEEKS = 4             # fewer normal weeks than this -> refuse to forecast
NORMAL_WEEK_SHARE = 0.5   # a week is "normal" if it has at least half the typical number of variable transactions
N_SIMS = 4000             # simulated futures
SEED = 0


class NotEnoughHistory(ValueError):
    """The statement is too short (or too irregular) to learn variable cash from."""


@dataclass
class History:
    """Daily variable cash from the statement. 'origin' is the last booked day: the forecast starts after it."""
    origin: pd.Timestamp
    sales: pd.Series       # variable money in per day, EUR
    costs: pd.Series       # variable money out per day, EUR (negative)
    activity: pd.Series    # number of variable transactions per day (to spot closed weeks)


def build_history(tx: pd.DataFrame, is_scheduled: pd.Series) -> History:
    days = pd.date_range(tx["date"].min(), tx["date"].max())
    var = tx[~is_scheduled]

    def daily(rows):
        return rows.groupby("date")["eur"].sum().reindex(days, fill_value=0.0)

    return History(
        origin=days[-1],
        sales=daily(var[var["eur"] > 0]),
        costs=daily(var[var["eur"] < 0]),
        activity=var.groupby("date").size().reindex(days, fill_value=0),
    )


def scheduled_amounts(dates: pd.DatetimeIndex, schedule: list[Payment], events: list[Event] = ()) -> np.ndarray:
    """Total scheduled payments on each date, with shift_amount events applied from their start date."""
    out = np.zeros(len(dates))
    for p in schedule:
        on = np.asarray(np.minimum(p.day, dates.days_in_month) == dates.day)
        if p.months is not None:
            on &= np.asarray(dates.month.isin(p.months))
        amount = np.full(len(dates), p.amount)
        for e in events:
            if isinstance(e, ShiftAmount) and e.stream == p.name:
                amount[np.asarray(dates >= pd.Timestamp(e.from_))] *= 1 + e.change_pct / 100
        out += np.where(on, amount, 0.0)
    return out


def simulate(history: History, schedule: list[Payment], start_balance: float, horizon: int,
             events: list[Event] = ()) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Return the forecast dates and an (N_SIMS, horizon) array of simulated end-of-day balances."""
    dates = pd.date_range(history.origin + pd.Timedelta(days=1), periods=horizon)
    weeks = _normal_weeks(history)
    week = pd.Timedelta(days=6)
    hist_sales = np.stack([history.sales[m:m + week].to_numpy() for m in weeks])   # (weeks, 7 weekdays)
    hist_costs = np.stack([history.costs[m:m + week].to_numpy() for m in weeks])

    # draw whole weeks; each forecast day takes the same weekday from its drawn week
    weekday = np.asarray(dates.day_of_week)
    week_no = (np.arange(horizon) + weekday[0]) // 7
    pick = np.random.default_rng(SEED).integers(0, len(weeks), (N_SIMS, week_no.max() + 1))
    sales = hist_sales[pick[:, week_no], weekday].astype(float)
    costs = hist_costs[pick[:, week_no], weekday].astype(float)

    # events on variable cash; one shared random level per simulated future for all scale events
    level = np.random.default_rng(SEED + 1).standard_normal(N_SIMS)[:, None]
    one_offs = np.zeros(horizon)
    for e in events:
        if isinstance(e, Scale):
            on = np.asarray((dates >= pd.Timestamp(e.from_)) & (dates <= pd.Timestamp(e.to or "2100-01-01")))
            factor = np.clip(e.factor_mean + e.factor_sd * level, 0.0, None)
            target = sales if e.flow == "sales" else costs
            target[:, on] *= factor
        elif isinstance(e, Closure):
            on = np.asarray((dates >= pd.Timestamp(e.from_)) & (dates <= pd.Timestamp(e.to)))
            sales[:, on] = 0.0
            costs[:, on] = 0.0
        elif isinstance(e, OneOff):
            one_offs[np.asarray(dates == pd.Timestamp(e.date))] += e.amount

    flows = sales + costs + scheduled_amounts(dates, schedule, events) + one_offs
    return dates, start_balance + flows.cumsum(axis=1)


def _normal_weeks(history: History) -> list[pd.Timestamp]:
    """Mondays of the last N_WEEKS full weeks with normal activity (skips closures, holidays, ...)."""
    six = pd.Timedelta(days=6)
    mondays = [d for d in history.activity.index if d.day_of_week == 0 and d + six <= history.origin]
    counts = np.array([history.activity[m:m + six].sum() for m in mondays])
    if len(mondays) == 0:
        raise NotEnoughHistory("the statement must cover at least one full Monday-Sunday week")
    normal = [m for m, c in zip(mondays, counts) if c >= NORMAL_WEEK_SHARE * np.median(counts)][-N_WEEKS:]
    if len(normal) < MIN_WEEKS:
        raise NotEnoughHistory(f"found {len(normal)} normal weeks in the statement, need at least {MIN_WEEKS}")
    return normal


# --- results -----------------------------------------------------------------------------------------

class DayBand(BaseModel):
    date: str
    p5: float
    p50: float
    p95: float


class LockAmount(BaseModel):
    days: int
    amount: float           # safe to lock for this many days, EUR
    lowest_balance: float   # pessimistic lowest balance within these days (the 'risk' percentile)


class Buffer(BaseModel):
    amount: float
    source: str             # "user" (sent in the request) or "suggested" (one month of scheduled payments)


class Scenario(BaseModel):
    events: list[Event]
    buffer: Buffer
    safe_to_lock: list[LockAmount]
    p_below_zero: float     # share of simulated futures where the balance goes below 0 at least once
    end_balance_p50: float
    daily: list[DayBand]


def suggested_buffer(schedule: list[Payment], start: pd.Timestamp, events: list[Event] = ()) -> float:
    """One month of scheduled money out: the next 12 months of scheduled payments (with events) divided by 12."""
    year = scheduled_amounts(pd.date_range(start, periods=365), schedule, events)
    return float(-year[year < 0].sum() / 12)


def run_scenario(history: History, schedule: list[Payment], start_balance: float, events: list[Event],
                 horizon: int, risk: float, buffer_eur: float | None, lock_days: list[int]) -> Scenario:
    """Simulate one scenario and turn it into the numbers the recommender needs.

    Safe to lock for d days = (lowest balance within d days that only `risk` of futures fall below) - buffer,
    never below 0. Money locked today is gone for all d days, so the lowest point matters, not the end balance.
    """
    dates, paths = simulate(history, schedule, start_balance, horizon, events)

    if buffer_eur is None:
        buffer = Buffer(amount=round(suggested_buffer(schedule, dates[0], events), 2), source="suggested")
    else:
        buffer = Buffer(amount=buffer_eur, source="user")

    locks = []
    for d in lock_days:
        low = float(np.percentile(paths[:, :d].min(axis=1), 100 * risk))
        locks.append(LockAmount(days=d, amount=round(max(0.0, low - buffer.amount), 2), lowest_balance=round(low, 2)))

    p5, p50, p95 = np.percentile(paths, [5, 50, 95], axis=0)
    return Scenario(
        events=list(events),
        buffer=buffer,
        safe_to_lock=locks,
        p_below_zero=round(float(np.mean((paths < 0).any(axis=1))), 4),
        end_balance_p50=round(float(p50[-1]), 2),
        daily=[DayBand(date=d.date().isoformat(), p5=round(a, 2), p50=round(b, 2), p95=round(c, 2))
               for d, a, b, c in zip(dates, p5, p50, p95)],
    )
