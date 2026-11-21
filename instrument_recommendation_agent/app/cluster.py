"""OpenShift entry point using the same NeMo policy, identity and MLflow configuration as the CFO chat."""

import json
from functools import lru_cache

import httpx
from langchain_openai import ChatOpenAI

from agent import AgentDecision, request_decision
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


def checked_decision(messages: list[dict]) -> AgentDecision | None:
    """Check the instrument context and trace the actual structured model call."""
    families = json.loads(messages[0]["content"])["eligible_families"]
    with trace_span("cfo.instrument_recommendation") as metadata:
        metadata["evaluated_offers"] = sum(len(family["variants"]) for family in families)
        metadata["eligible_families"] = len(families)
        get_guardrails_client().check([message["content"] for message in messages])
        with trace_span("qwen.structured_notification") as call:
            call["model"] = get_settings().llm_model
            return request_decision(messages, cluster_model())


app.state.request_decision = checked_decision
