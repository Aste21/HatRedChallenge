import datetime
import time
from functools import lru_cache

from pydantic import BaseModel

from app.config import get_settings
from app.service_client import ServiceClient, ServiceUnavailableError

FORECAST_CACHE_SECONDS = 60
FAILURE_CACHE_SECONDS = 15


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


class Scenario(BaseModel):
    """One forecast scenario as returned by the forecast service."""

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

    def __init__(self, service_client: ServiceClient, account_id: str) -> None:
        """Bind the client to one account.

        Args:
            service_client: HTTP client pointed at the forecast service.
            account_id: Account id known to the forecast service.
        """
        self._service_client = service_client
        self._account_id = account_id
        self._cache: dict[int, tuple[float, Forecast | ServiceUnavailableError]] = {}

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
            1. Reuse a recent answer: every page and chat message needs the forecast, but it only changes
               when a new statement is uploaded. A recent failure is reused too, so a service that is
               down does not slow down every page by the connection timeout.
            2. Otherwise ask the forecast service and remember the forecast or the failure.
        """
        cached = self._cache.get(horizon_days)
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
                json={"account_id": self._account_id, "horizon": horizon_days, "lock_days": lock_days},
            )
        except ServiceUnavailableError as error:
            self._cache[horizon_days] = (time.monotonic(), error)
            raise
        forecast = Forecast.model_validate(payload)
        self._cache[horizon_days] = (time.monotonic(), forecast)
        return forecast


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
    )
