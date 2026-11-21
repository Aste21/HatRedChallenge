from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "var" / "autonomous-cfo.sqlite3"


class Settings(BaseSettings):
    """Runtime configuration read from environment variables (or a local `.env` file in dev).

    Attributes:
        llm_base_url: OpenAI-compatible base URL of the vLLM server, ending in `/v1`.
        llm_model: Model id as returned by `GET /v1/models`. Empty means "use the first served model".
        llm_api_key: Service-account token for the inference endpoint.
        llm_ca_bundle: Path to a CA bundle that signs the cluster-internal certificate.
        llm_verify_tls: Set to false only in local dev when no CA bundle is available.
        llm_timeout_seconds: Request timeout for a single LLM call.
        database_path: SQLite file for chat history (mount a PVC at its directory in-cluster).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_base_url: str
    llm_model: str = ""
    llm_api_key: str = "EMPTY"
    llm_ca_bundle: str = ""
    llm_verify_tls: bool = True
    llm_timeout_seconds: float = 60.0
    database_path: Path = DEFAULT_DATABASE_PATH


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process.

    Returns:
        The cached application settings.
    """
    return Settings()
