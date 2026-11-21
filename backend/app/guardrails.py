"""Standalone input checks against the cluster NeMo service."""

from functools import lru_cache

import httpx
from fastapi import HTTPException

from app.config import Settings, get_settings
from app.tracing import trace_span


class GuardrailsClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.Client(
            verify=settings.llm_ca_bundle or settings.llm_verify_tls,
            timeout=settings.guardrails_timeout_seconds,
        )

    def check(self, content: list[str]) -> None:
        """Check dynamic prompt material as input, including retrieved or browser-provided context."""
        if not self.settings.guardrails_url or not content:
            return
        with trace_span("guardrails.input") as metadata:
            metadata["decision"] = "unavailable"
            try:
                response = self.client.post(
                    self.settings.guardrails_url.rstrip("/") + "/v1/guardrail/checks",
                    json={
                        "model": self.settings.llm_model or "cfo",
                        "messages": [{"role": "user", "content": "\n\n".join(content)}],
                    },
                    headers={"Authorization": f"Bearer {self.settings.service_token()}"},
                )
                response.raise_for_status()
                payload = response.json()
                decision = payload.get("status") if isinstance(payload, dict) else None
            except (httpx.HTTPError, OSError, ValueError):
                decision = None
            if decision == "blocked":
                metadata["decision"] = "blocked"
                raise HTTPException(
                    422, "Remove sensitive details from the message or its context and try again."
                )
            if decision != "success":
                raise HTTPException(503, "The safety check is unavailable. Please try again shortly.")
            metadata["decision"] = "success"


@lru_cache
def get_guardrails_client() -> GuardrailsClient:
    return GuardrailsClient(get_settings())
