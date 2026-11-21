from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.forecasting.client import ForecastClient, get_forecast_client
from app.service_client import ServiceUnavailableError
from app.storage.decisions import now_iso
from app.storage.news_impacts import NewsImpact, NewsImpactRepository, get_news_impact_repository

router = APIRouter(prefix="/api/news", tags=["news"])

ARTICLE_ID_PATTERN = r"^[a-f0-9]{8,64}$"


class NewsImpactRequest(BaseModel):
    """An article the owner wants the forecast to take into account."""

    article_id: str = Field(pattern=ARTICLE_ID_PATTERN)
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=4000)


class NewsImpactList(BaseModel):
    """The news impacts the forecast currently takes into account."""

    impacts: list[NewsImpact]


@router.get("/impacts", response_model=NewsImpactList)
def list_news_impacts(
    repository: Annotated[NewsImpactRepository, Depends(get_news_impact_repository)],
) -> NewsImpactList:
    """List the articles applied to the forecast with the events derived from them.

    Args:
        repository: Injected news impact store.

    Returns:
        The applied news impacts.
    """
    return NewsImpactList(impacts=repository.list_impacts())


@router.post("/impacts", response_model=NewsImpact)
def apply_news_impact(
    request: NewsImpactRequest,
    forecast_client: Annotated[ForecastClient, Depends(get_forecast_client)],
    repository: Annotated[NewsImpactRepository, Depends(get_news_impact_repository)],
) -> NewsImpact:
    """Turn an article into forecast events and include them in every following forecast.

    Args:
        request: The article.
        forecast_client: Injected forecast client, which also turns news into events.
        repository: Injected news impact store.

    Returns:
        The stored impact; `events` is empty when the article does not change the cash flow.

    Steps:
        1. Ask the forecast service (LLM + checks) which events the article implies for this account.
        2. Store them, also when there are none, so the page can say "no effect on your forecast".
    """
    news_text = f"{request.title}\n\n{request.summary}".strip()
    try:
        derived = forecast_client.events_from_news(news_text)
    except ServiceUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    impact = NewsImpact(
        article_id=request.article_id,
        title=request.title,
        events=derived.events,
        rejected_count=derived.rejected_count,
        created_at=now_iso(),
    )
    repository.save_impact(impact)
    return impact


@router.delete("/impacts/{article_id}", status_code=204)
def remove_news_impact(
    article_id: str,
    repository: Annotated[NewsImpactRepository, Depends(get_news_impact_repository)],
) -> Response:
    """Stop taking an article into account in the forecast.

    Args:
        article_id: Id of the article.
        repository: Injected news impact store.

    Returns:
        An empty 204 response.
    """
    if not repository.delete_impact(article_id):
        raise HTTPException(status_code=404, detail="This article is not part of the forecast.")
    return Response(status_code=204)
