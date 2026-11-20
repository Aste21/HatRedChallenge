"""Settings, read once from environment variables.

LLM (an OpenAI-compatible endpoint, e.g. vLLM served on Red Hat OpenShift AI):
    LLM_BASE_URL    base URL up to and including /v1, e.g. https://my-model-myproject.apps.example.com/v1
    LLM_API_KEY     bearer token of the model endpoint (leave empty if token auth is off)
    LLM_MODEL       served model name, as listed by GET {LLM_BASE_URL}/models
    LLM_VERIFY_TLS  "true" (default), "false" (self-signed cluster certificates), or a path to a CA bundle file
    LLM_TIMEOUT_S   seconds to wait for the model (default 60; CPU-only models are slow)
    LLM_MAX_TOKENS  maximum length of the model's reply (default 1000)
    LLM_JSON_MODE   "true" (default) asks the server for JSON output via response_format

Storage:
    DATA_DIR        folder with one sub-folder per account (default ./data)
"""
import os
from dataclasses import dataclass


def _verify_tls(value: str) -> bool | str:
    """'true'/'false' -> bool; anything else is treated as a path to a CA bundle."""
    if value.lower() in ("true", "1", "yes", ""):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    return value


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_verify_tls: bool | str
    llm_timeout_s: float
    llm_max_tokens: int
    llm_json_mode: bool
    data_dir: str

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)


def load_settings() -> Settings:
    env = os.environ.get
    return Settings(
        llm_base_url=env("LLM_BASE_URL", "").rstrip("/"),
        llm_api_key=env("LLM_API_KEY", ""),
        llm_model=env("LLM_MODEL", ""),
        llm_verify_tls=_verify_tls(env("LLM_VERIFY_TLS", "true")),
        llm_timeout_s=float(env("LLM_TIMEOUT_S", "60")),
        llm_max_tokens=int(env("LLM_MAX_TOKENS", "1000")),
        llm_json_mode=env("LLM_JSON_MODE", "true").lower() in ("true", "1", "yes"),
        data_dir=env("DATA_DIR", "data"),
    )
