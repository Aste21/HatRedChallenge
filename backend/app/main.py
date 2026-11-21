import logging

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.forecast import router as forecast_router
from app.api.news import router as news_router
from app.api.proposals import router as proposals_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Autonomous CFO")
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
