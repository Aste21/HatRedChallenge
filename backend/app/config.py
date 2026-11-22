from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "var" / "autonomous-cfo.sqlite3"


class MailSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    owner_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


class Settings(MailSettings):
    """Runtime configuration read from environment variables (or a local `.env` file in dev).

    Attributes:
        llm_base_url: OpenAI-compatible base URL of the vLLM server, ending in `/v1`.
        llm_model: Model id as returned by `GET /v1/models`. Empty means "use the first served model".
        llm_api_key: Service-account token for the inference endpoint.
        llm_ca_bundle: Path to a CA bundle that signs the cluster-internal certificate.
        llm_verify_tls: Set to false only in local dev when no CA bundle is available.
        llm_timeout_seconds: Request timeout for a single LLM call.
        database_path: SQLite file for chat history, decisions and the notification outbox
            (mount a PVC at its directory in-cluster).
        forecast_api_url: Base URL of the forecast service (`account-prediction/`). Empty = not connected.
        instrument_api_url: Base URL of the instrument recommendation agent. Empty = not connected.
        news_api_url: Base URL of the news service (`news/`). Empty = not connected.
        service_timeout_seconds: Timeout for calls to the forecast and news services.
        instrument_timeout_seconds: Timeout for the instrument agent, which calls the LLM itself.
        owner_email: Primary recipient of notifications.
        approval_copy_email: Optional blind-copy recipient for approval confirmations.
        investment_alert_api_url: Backend URL for periodic investment alerts. Empty disables them.
        smtp_host: SMTP server; when empty, notifications stay in the in-app outbox only.
        smtp_port: SMTP port (STARTTLS).
        smtp_user: SMTP login, also used as the sender address.
        smtp_password: SMTP password.
    """

    approval_copy_email: str = ""
    investment_alert_api_url: str = ""
    llm_base_url: str
    llm_model: str = ""
    llm_api_key: str = "EMPTY"
    service_token_file: Path | None = None
    guardrails_url: str = ""
    guardrails_timeout_seconds: float = 12.0
    llm_ca_bundle: str = ""
    llm_verify_tls: bool = True
    llm_timeout_seconds: float = 60.0
    database_path: Path = DEFAULT_DATABASE_PATH
    forecast_api_url: str = ""
    instrument_api_url: str = ""
    news_api_url: str = ""
    service_timeout_seconds: float = 10.0
    instrument_timeout_seconds: float = 120.0

    def service_token(self) -> str:
        """Read the current projected pod token, or the configured local credential."""
        if self.service_token_file:
            return self.service_token_file.read_text(encoding="utf-8").strip()
        return self.llm_api_key


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process.

    Returns:
        The cached application settings.
    """
    return Settings()
