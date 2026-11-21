import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ServiceUnavailableError(RuntimeError):
    """A team service (forecast, instrument agent, news) is not configured, not reachable or failed."""


class ServiceClient:
    """Small JSON-over-HTTP client for one of the team's in-cluster services."""

    def __init__(self, service_name: str, base_url: str, timeout_seconds: float) -> None:
        """Remember where the service lives.

        Args:
            service_name: Human-readable name used in log and error messages.
            base_url: Base URL of the service; empty means the service is not connected.
            timeout_seconds: Timeout for a single request.
        """
        self.service_name = service_name
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        """Whether a base URL was configured for this service.

        Returns:
            `True` if the service can be called.
        """
        return bool(self._base_url)

    def request_json(
        self, method: str, path: str, timeout_seconds: float | None = None, **request_options: Any
    ) -> Any:
        """Call the service and return the decoded JSON body.

        Args:
            method: HTTP method, e.g. `GET` or `POST`.
            path: Path relative to the base URL, starting with `/`.
            timeout_seconds: Timeout for this request; defaults to the client's timeout. Endpoints that
                call the LLM need a longer one.
            **request_options: Passed to `httpx.request` (`json`, `params`, ...).

        Returns:
            The decoded JSON response.

        Steps:
            1. Refuse early when the service is not configured.
            2. Send the request with the configured timeout.
            3. Turn network errors, HTTP errors and invalid JSON into `ServiceUnavailableError`.
        """
        if not self.configured:
            raise ServiceUnavailableError(f"The {self.service_name} is not connected.")
        try:
            response = httpx.request(
                method,
                f"{self._base_url}{path}",
                timeout=timeout_seconds or self._timeout_seconds,
                **request_options,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            logger.warning(
                "%s answered %s: %s", self.service_name, error.response.status_code, error.response.text[:300]
            )
            raise ServiceUnavailableError(f"The {self.service_name} answered with an error.") from error
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("%s is not reachable: %s", self.service_name, error)
            raise ServiceUnavailableError(f"The {self.service_name} is not reachable right now.") from error
