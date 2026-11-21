import threading
import time

from app.service_client import ServiceClient, ServiceUnavailableError

DEFAULT_LOCK_DAYS = (30, 60, 90)
TERMS_CACHE_SECONDS = 15 * 60
TERMS_FAILURE_CACHE_SECONDS = 60


class OfferTermsClient:
    """Asks the instrument agent which terms its catalog offers, so the forecast prices exactly those."""

    def __init__(self, service_client: ServiceClient) -> None:
        """Wrap the HTTP client.

        Args:
            service_client: HTTP client pointed at the instrument agent.
        """
        self._service_client = service_client
        self._lock = threading.Lock()
        self._cached: tuple[float, float, tuple[int, ...]] | None = None

    def lock_days(self) -> tuple[int, ...]:
        """The offer terms in days, or the default 30/60/90 when the agent cannot be asked.

        Returns:
            Sorted, distinct terms in days.

        Steps:
            1. Reuse the last answer while it is fresh (a failure is reused for a minute, so a stopped
               agent does not slow down every forecast by the connection timeout).
            2. Otherwise call `GET /offer-terms` and keep only positive whole days.
            3. Fall back to the default terms when the agent is down or returns nothing usable.
        """
        with self._lock:
            if self._cached is not None:
                stored_at, max_age, terms = self._cached
                if time.monotonic() - stored_at < max_age:
                    return terms
            try:
                payload = self._service_client.request_json("GET", "/offer-terms")
                terms = tuple(sorted({int(days) for days in payload["term_days"] if int(days) > 0}))
            except (ServiceUnavailableError, KeyError, TypeError, ValueError):
                terms = ()
            if terms:
                self._cached = (time.monotonic(), TERMS_CACHE_SECONDS, terms)
            else:
                terms = DEFAULT_LOCK_DAYS
                self._cached = (time.monotonic(), TERMS_FAILURE_CACHE_SECONDS, terms)
            return terms
