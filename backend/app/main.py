import asyncio
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from pydantic import ValidationError

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.dashboard_defaults import router as dashboard_defaults_router
from app.api.forecast import router as forecast_router
from app.api.news import router as news_router
from app.api.proposals import router as proposals_router
from app.config import get_settings
from app.notifications.balance_alerts import monitor_investments
from app.notifications.email import smtp_configured
from app.storage.conversations import get_conversation_repository
from app.storage.sample_conversations import seed_sample_conversations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Seed sample conversations and manage the optional investment monitor.

    Args:
        application: The FastAPI app being started.

    Returns:
        A context manager that runs for the app's lifetime.

    Steps:
        1. Seed sample conversations for newly initialized accounts.
        2. Start investment monitoring when configured and cancel it at shutdown.
    """
    # Sample data is a convenience: a missing setting or a storage problem must never stop the app.
    try:
        seeded_accounts = seed_sample_conversations(get_conversation_repository())
    except (ValidationError, sqlite3.Error, OSError):
        logger.warning("Sample conversations could not be seeded", exc_info=True)
        seeded_accounts = []
    if seeded_accounts:
        logger.info("Seeded sample conversations for %s", ", ".join(seeded_accounts))
    try:
        settings = get_settings()
    except ValidationError:
        settings = None
    monitor = None
    if (
        settings
        and settings.investment_alert_api_url
        and smtp_configured(settings)
        and settings.smtp_password
    ):
        monitor = asyncio.create_task(monitor_investments(settings))
    try:
        yield
    finally:
        if monitor is not None:
            monitor.cancel()
            with suppress(asyncio.CancelledError):
                await monitor


app = FastAPI(
    title="CFOcus",
    description="CFOcus backend: forecast, proposals, approvals, notifications and chat for SME owners.",
    lifespan=lifespan,
)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(dashboard_defaults_router)
app.include_router(forecast_router)
app.include_router(news_router)
app.include_router(proposals_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe for OpenShift.

    Returns:
        A static OK payload.
    """
    return {"status": "ok"}
