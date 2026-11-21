import datetime
import json
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.config import get_settings
from app.service_client import ServiceClient, ServiceUnavailableError
from app.storage.news_impacts import get_news_impact_repository

FORECAST_CACHE_SECONDS = 60
FAILURE_CACHE_SECONDS = 15
MAX_NEWS_TEXT_LENGTH = 5000


class DailyBand(BaseModel):
    """Forecast balance for one day: pessimistic (p5), median (p50) and optimistic (p95), in EUR."""

    date: datetime.date
    p5: float
    p50: float
    p95: float


class SafeToLock(BaseModel):
    """Cash that can be locked away for `days` without dipping into the buffer (pessimistic case)."""

    days: int
    amount: float
    lowest_balance: float


class CashBuffer(BaseModel):
    """Cash the owner always keeps; `suggested` means one month of scheduled payments."""

    amount: float
    source: str


class ForecastEvent(BaseModel):
    """A checked change to future cash flow (from news) that a scenario took into account.

    Only the fields every event type shares are typed; the type-specific fields (`stream`, `from`, `to`,
    `change_pct`, `amount`, `factor_mean`, ...) are kept as they are so they can be shown and sent back.
    """

    model_config = ConfigDict(extra="allow")

    type: Literal["shift_amount", "one_off", "scale", "closure"]
    certainty: Literal["official", "assumption"]
    why: str = ""


class Scenario(BaseModel):
    """One forecast scenario as returned by the forecast service."""

    events: list[ForecastEvent] = []
    buffer: CashBuffer
    safe_to_lock: list[SafeToLock]
    p_below_zero: float
    end_balance_p50: float
    daily: list[DailyBand]


class ScheduledPayment(BaseModel):
    """A recurring payment the forecast service detected in the statement."""

    name: str
    day: int
    months: list[int] | None
    amount: float
    counterparty: str | None = None
    last_reference: str | None = None
    last_date: datetime.date | None = None


class NewsEvents(BaseModel):
    """Events the forecast service derived from one news item, and how many proposals failed its checks."""

    events: list[dict[str, Any]]
    rejected_count: int


class Forecast(BaseModel):
    """Balance forecast for the business account (subset of the forecast service's response)."""

    account_id: str
    as_of: datetime.date
    start_balance: float
    schedule: list[ScheduledPayment]
    official: Scenario
    with_assumptions: Scenario


class ForecastClient:
    """Calls the balance forecast service (`account-prediction/`)."""

    def __init__(
        self,
        service_client: ServiceClient,
        account_id: str,
        load_events: Callable[[], list[dict[str, Any]]],
        news_timeout_seconds: float,
    ) -> None:
        """Bind the client to one account.

        Args:
            service_client: HTTP client pointed at the forecast service.
            account_id: Account id known to the forecast service.
            load_events: Returns the news events the owner applied; they are sent with every forecast.
            news_timeout_seconds: Timeout for turning news into events, which calls the LLM.
        """
        self._service_client = service_client
        self._account_id = account_id
        self._load_events = load_events
        self._news_timeout_seconds = news_timeout_seconds
        self._cache: dict[tuple[int, str], tuple[float, Forecast | ServiceUnavailableError]] = {}

    @property
    def configured(self) -> bool:
        """Whether the forecast service URL is configured.

        Returns:
            `True` if forecasts can be requested.
        """
        return self._service_client.configured

    def fetch_forecast(self, horizon_days: int = 90) -> Forecast:
        """Forecast the account balance for the next days.

        Args:
            horizon_days: Number of days to forecast (7–365).

        Returns:
            The forecast with daily bands and the safe-to-lock amounts for 30/60/90 days.

        Steps:
            1. Load the news events the owner applied; they are part of the cache key.
            2. Reuse a recent answer: every page and chat message needs the forecast, but it only changes
               when a new statement is uploaded or news is applied. A recent failure is reused too, so a
               service that is down does not slow down every page by the connection timeout.
            3. Otherwise ask the forecast service and remember the forecast or the failure.
        """
        events = self._load_events()
        cache_key = (horizon_days, json.dumps(events, sort_keys=True))
        cached = self._cache.get(cache_key)
        if cached is not None:
            stored_at, result = cached
            max_age = (
                FAILURE_CACHE_SECONDS
                if isinstance(result, ServiceUnavailableError)
                else FORECAST_CACHE_SECONDS
            )
            if time.monotonic() - stored_at < max_age:
                if isinstance(result, ServiceUnavailableError):
                    raise result
                return result

        lock_days = [days for days in (30, 60, 90) if days <= horizon_days] or [horizon_days]
        try:
            payload = self._service_client.request_json(
                "POST",
                "/forecast",
                json={
                    "account_id": self._account_id,
                    "horizon": horizon_days,
                    "lock_days": lock_days,
                    "events": events,
                },
            )
        except ServiceUnavailableError as error:
            self._cache[cache_key] = (time.monotonic(), error)
            raise
        forecast = Forecast.model_validate(payload)
        self._cache[cache_key] = (time.monotonic(), forecast)
        return forecast

    def events_from_news(self, news_text: str) -> NewsEvents:
        """Ask the forecast service how one news item changes this account's future cash flow.

        Args:
            news_text: Headline and summary of the article.

        Returns:
            The checked events (possibly none) and the number of events that failed the checks.
        """
        payload = self._service_client.request_json(
            "POST",
            "/news/events",
            timeout_seconds=self._news_timeout_seconds,
            json={"account_id": self._account_id, "news": news_text[:MAX_NEWS_TEXT_LENGTH]},
        )
        return NewsEvents(events=payload.get("events", []), rejected_count=len(payload.get("rejected", [])))


@lru_cache
def get_forecast_client() -> ForecastClient:
    """Create the forecast client once per process.

    Returns:
        The shared forecast client.
    """
    settings = get_settings()
    return ForecastClient(
        ServiceClient("forecast service", settings.forecast_api_url, settings.service_timeout_seconds),
        settings.account_id,
        get_news_impact_repository().all_events,
        settings.instrument_timeout_seconds,
    )
