"""OpenShift entry point using the same NeMo policy, identity and MLflow configuration as the CFO chat."""

import json
from datetime import date
from functools import lru_cache

import httpx
from langchain_openai import ChatOpenAI

from agent import NotificationDraft, draft_notification
from app.config import get_settings
from app.guardrails import get_guardrails_client
from app.llm import ServiceAccountAuth
from app.tracing import trace_span
from instrument_api import app


@lru_cache
def cluster_model() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model, base_url=settings.llm_base_url,
        api_key=settings.service_token, temperature=0, timeout=45, max_retries=1,
        http_client=httpx.Client(verify=settings.llm_ca_bundle, auth=ServiceAccountAuth(settings)),
    )


def checked_draft(*, as_of: date, evaluations: list[dict]) -> NotificationDraft:
    """Validate the financial tool results before requesting a structured notification."""
    payload = {"as_of": as_of.isoformat(), "currency": "EUR", "evaluations": evaluations}
    with trace_span("cfo.instrument_recommendation") as metadata:
        metadata["evaluated_offers"] = len(evaluations)
        get_guardrails_client().check([json.dumps(payload)])
        with trace_span("qwen.structured_notification") as call:
            call["model"] = get_settings().llm_model
            return draft_notification(as_of=as_of, evaluations=evaluations, model=cluster_model())


app.state.draft_notification = checked_draft
