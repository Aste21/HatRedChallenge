import logging
from collections.abc import Callable
from functools import partial
from typing import Annotated

from fastapi import Depends

from app.accounts import AccountProfile, get_account
from app.agents.investment.agent import format_euro
from app.agents.news.client import NewsClient, get_news_client
from app.forecasting.client import Forecast, ForecastClient, get_forecast_client
from app.service_client import ServiceUnavailableError
from app.storage.decisions import DecisionRepository, get_decision_repository
from app.tracing import trace_span

logger = logging.getLogger(__name__)

MAX_NEWS_ITEMS = 5
MAX_TRANSACTIONS = 5


def _forecast_lines(forecast: Forecast) -> list[str]:
    """Describe the forecast in a few lines for the chat prompt.

    Args:
        forecast: The current balance forecast.

    Returns:
        Prompt lines with the forecast figures.
    """
    scenario = forecast.official
    lowest_day = min(scenario.daily, key=lambda band: band.p5)
    lines = [
        f"Balance on {forecast.as_of.isoformat()} (last booking): {format_euro(forecast.start_balance)}.",
        f"Forecast for the next {len(scenario.daily)} days: expected balance at the end "
        f"{format_euro(scenario.end_balance_p50)}; lowest balance in a bad case {format_euro(lowest_day.p5)} "
        f"on {lowest_day.date.isoformat()}; chance of going below zero {scenario.p_below_zero:.0%}.",
        f"Cash buffer to keep: {format_euro(scenario.buffer.amount)}"
        + (" (one month of scheduled payments)." if scenario.buffer.source == "suggested" else "."),
        "Safe to put into a deposit: "
        + "; ".join(f"{limit.days} days {format_euro(limit.amount)}" for limit in scenario.safe_to_lock)
        + ".",
        "Scheduled payments: "
        + "; ".join(
            f"{payment.name} {format_euro(payment.amount)} on day {payment.day}"
            + (f" (months {', '.join(map(str, payment.months))})" if payment.months else "")
            for payment in forecast.schedule
        )
        + ".",
    ]
    if forecast.with_assumptions.events:
        lines.append(
            "News the forecast takes into account: "
            + "; ".join(
                f"{event.why or event.type} ({event.certainty})" for event in forecast.with_assumptions.events
            )
            + ". Official changes are in the figures above; assumptions only in the 'with assumptions' "
            f"scenario (expected end balance {format_euro(forecast.with_assumptions.end_balance_p50)})."
        )
    return lines


def build_business_snapshot(
    account_id: str, forecast_client: ForecastClient, news_client: NewsClient, repository: DecisionRepository
) -> str:
    """Collect the latest figures from the team's services so the chat can answer with real numbers.

    Args:
        account_id: The signed-in account.
        forecast_client: Client for the forecast service.
        news_client: Client for the news service.
        repository: Store with simulated transactions.

    Returns:
        A compact text block for the system prompt; empty if no data source is available.

    Steps:
        1. Add the forecast summary (balance, bands, buffer, safe-to-lock, scheduled payments).
        2. Add the simulated actions the owner already approved.
        3. Add the headlines of relevant business news.
        Each source is optional: if a service is down, its section is left out.
    """
    with trace_span("cfo.business_context") as summary:
        lines: list[str] = []
        with trace_span("forecast.fetch") as forecast:
            forecast["status"] = "unconfigured"
            if forecast_client.configured:
                try:
                    result = forecast_client.fetch_forecast(account_id, trace_attributes=forecast)
                    lines.extend(_forecast_lines(result))
                    forecast["status"] = "ok"
                except ServiceUnavailableError as error:
                    forecast.update(status="error", error_type=type(error).__name__)
                    lines.append("The balance forecast is not available right now.")
        summary["forecast_status"] = forecast["status"]

        transactions = repository.list_transactions(account_id)[:MAX_TRANSACTIONS]
        if transactions:
            lines.append(
                "Already approved (simulated, no real money moved): "
                + "; ".join(
                    f"{transaction.description} on {transaction.created_at[:10]}"
                    for transaction in transactions
                )
                + "."

            )

        with trace_span("news.fetch") as news:
            news["status"] = "unconfigured"
            if news_client.configured:
                try:
                    articles = news_client.fetch_relevant_articles(MAX_NEWS_ITEMS)
                except ServiceUnavailableError as error:
                    news.update(status="error", error_type=type(error).__name__)
                else:
                    news.update(status="ok", article_count=len(articles))
                    summary["article_count"] = len(articles)
                    if articles:
                        lines.append("Relevant business news:")
                        lines.extend(
                            f"- {article.title} ({article.source})"
                            + (f": {article.reason}" if article.reason else "")
                            for article in articles
                        )
        summary["news_status"] = news["status"]
        return "\n".join(lines)


def get_business_snapshot(
    account: Annotated[AccountProfile, Depends(get_account)],
    forecast_client: Annotated[ForecastClient, Depends(get_forecast_client)],
    news_client: Annotated[NewsClient, Depends(get_news_client)],
    repository: Annotated[DecisionRepository, Depends(get_decision_repository)],
) -> Callable[[], str]:
    """Defer snapshot retrieval until the incoming chat message passes the input checks.

    Args:
        account: The signed-in account.
        forecast_client: Injected forecast client.
        news_client: Injected news client.
        repository: Injected decision store.

    Returns:
        The snapshot text.
    """
    return partial(build_business_snapshot, account.id, forecast_client, news_client, repository)
