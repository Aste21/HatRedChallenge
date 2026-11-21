import logging
from functools import lru_cache

import httpx
from openai import OpenAI

from app.config import Settings, get_settings
from app.tracing import trace_span

logger = logging.getLogger(__name__)


class ServiceAccountAuth(httpx.Auth):
    """Supply the current projected service account token on each HTTP request."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self.settings.service_token()}"
        yield request


class LlmClient:
    """Thin wrapper around the OpenAI-compatible client pointed at the in-cluster vLLM server."""

    def __init__(self, settings: Settings) -> None:
        """Create the HTTP and OpenAI clients.

        Args:
            settings: Application settings with the LLM endpoint configuration.
        """
        if settings.llm_ca_bundle:
            tls_verification: str | bool = settings.llm_ca_bundle
        else:
            tls_verification = settings.llm_verify_tls
        if tls_verification is False:
            logger.warning("TLS verification for the LLM endpoint is DISABLED (LLM_VERIFY_TLS=false).")

        self._client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
            http_client=httpx.Client(verify=tls_verification, auth=ServiceAccountAuth(settings)),
        )
        self._model = settings.llm_model

    @property
    def model(self) -> str:
        """Model id used for completions, discovered from `/v1/models` when not configured.

        Returns:
            The model id.
        """
        if not self._model:
            self._model = self._client.models.list().data[0].id
            logger.info("LLM_MODEL not set, using first served model: %s", self._model)
        return self._model

    def complete(
        self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int | None = None
    ) -> str:
        """Send a chat completion request and return the assistant's text.

        Args:
            messages: Chat messages in OpenAI format (`role` + `content`).
            temperature: Sampling temperature.
            max_tokens: Upper bound for the reply length; `None` lets the server decide.

        Returns:
            The assistant reply text (empty string if the model returned nothing).
        """
        with trace_span("qwen.completion") as metadata:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            metadata["model"] = response.model
            if response.usage:
                metadata["prompt_tokens"] = response.usage.prompt_tokens
                metadata["completion_tokens"] = response.usage.completion_tokens
            return response.choices[0].message.content or ""


@lru_cache
def get_llm_client() -> LlmClient:
    """Create the LLM client once per process.

    Returns:
        The shared LLM client.
    """
    return LlmClient(get_settings())
