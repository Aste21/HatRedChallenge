from functools import lru_cache

from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.service_client import ServiceClient, ServiceUnavailableError


class NewsArticle(BaseModel):
    """An article the news service accepted as relevant for the business."""

    title: str
    source: str
    url: str
    published: str | None = None
    reason: str | None = None


class NewsClient:
    """Reads accepted articles from the news service (`news/`)."""

    def __init__(self, service_client: ServiceClient) -> None:
        """Wrap the HTTP client.

        Args:
            service_client: HTTP client pointed at the news service.
        """
        self._service_client = service_client

    @property
    def configured(self) -> bool:
        """Whether the news service URL is configured.

        Returns:
            `True` if articles can be requested.
        """
        return self._service_client.configured

    def fetch_relevant_articles(self, limit: int = 10) -> list[NewsArticle]:
        """List the newest articles the news agent marked as relevant.

        Args:
            limit: Maximum number of articles.

        Returns:
            The accepted articles, newest first.
        """
        payload = self._service_client.request_json(
            "GET", "/articles", params={"status": "accepted", "limit": limit}
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
            raise ServiceUnavailableError("The news service returned an invalid article list.")
        try:
            return [NewsArticle.model_validate(article) for article in payload["articles"]]
        except ValidationError as error:
            raise ServiceUnavailableError("The news service returned an invalid article.") from error


@lru_cache
def get_news_client() -> NewsClient:
    """Create the news client once per process.

    Returns:
        The shared news client.
    """
    settings = get_settings()
    return NewsClient(ServiceClient("news service", settings.news_api_url, settings.service_timeout_seconds))
