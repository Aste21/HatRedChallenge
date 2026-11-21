import logging
from functools import lru_cache
from typing import Any

import httpx
from openai import OpenAI
from pydantic import BaseModel

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ToolCall(BaseModel):
    """A function call requested by the model."""

    id: str
    name: str
    arguments: str


class LlmReply(BaseModel):
    """The model's text plus any tool calls it made."""

    content: str
    tool_calls: list[ToolCall]


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
            http_client=httpx.Client(verify=tls_verification),
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
        self, messages: list[dict[str, Any]], temperature: float = 0.2, max_tokens: int | None = None
    ) -> str:
        """Send a chat completion request and return the assistant's text.

        Args:
            messages: Chat messages in OpenAI format (`role` + `content`, or tool calls and results).
            temperature: Sampling temperature.
            max_tokens: Upper bound for the reply length; `None` lets the server decide.

        Returns:
            The assistant reply text (empty string if the model returned nothing).
        """
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def complete_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], temperature: float = 0.2
    ) -> LlmReply:
        """Send a chat completion request in which the model may call one of the given tools.

        Args:
            messages: Chat messages in OpenAI format.
            tools: Tool definitions in OpenAI format.
            temperature: Sampling temperature.

        Returns:
            The reply text and the function calls the model made.
        """
        response = self._client.chat.completions.create(
            model=self.model, messages=messages, tools=tools, tool_choice="auto", temperature=temperature
        )
        message = response.choices[0].message
        return LlmReply(
            content=message.content or "",
            tool_calls=[
                ToolCall(id=call.id, name=call.function.name, arguments=call.function.arguments or "")
                for call in message.tool_calls or []
                if call.type == "function"
            ],
        )


@lru_cache
def get_llm_client() -> LlmClient:
    """Create the LLM client once per process.

    Returns:
        The shared LLM client.
    """
    return LlmClient(get_settings())
