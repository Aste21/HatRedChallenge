import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import ValidationError

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.forecast import router as forecast_router
from app.api.news import router as news_router
from app.api.proposals import router as proposals_router
from app.storage.conversations import get_conversation_repository
from app.storage.sample_conversations import seed_sample_conversations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Prepare the app on startup: give accounts that were never seeded their sample conversations.

    Args:
        application: The FastAPI app being started.

    Returns:
        A context manager that runs for the app's lifetime.
    """
    # Sample data is a convenience: a missing setting or a storage problem must never stop the app.
    try:
        seeded_accounts = seed_sample_conversations(get_conversation_repository())
    except (ValidationError, sqlite3.Error, OSError):
        logger.warning("Sample conversations could not be seeded", exc_info=True)
        seeded_accounts = []
    if seeded_accounts:
        logger.info("Seeded sample conversations for %s", ", ".join(seeded_accounts))
    yield


app = FastAPI(
    title="CFOcus",
    description="CFOcus backend: forecast, proposals, approvals, notifications and chat for SME owners.",
    lifespan=lifespan,
)
app.include_router(chat_router)
app.include_router(conversations_router)
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
