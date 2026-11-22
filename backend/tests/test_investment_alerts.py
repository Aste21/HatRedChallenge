from pathlib import Path
from unittest.mock import patch

import httpx

from app.config import Settings
from app.notifications.balance_alerts import check_accounts


def test_investment_alert_is_sent_once_without_other_alerts(tmp_path: Path) -> None:
    settings = Settings(llm_base_url="http://llm", database_path=tmp_path / "cfo.sqlite3")
    forecast = {
        "account_id": "amalfi",
        "as_of": "2025-12-31",
        "start_balance": 10000,
        "official": {
            "daily": [{"date": "2026-03-01", "p50": -100}],
            "safe_to_lock": [{"days": 30, "amount": 6000}],
        },
    }
    placement = {
        "kind": "fixed_term_deposit",
        "status": "approved",
        "term_days": 30,
        "amount": 5000,
    }
    board = {
        "as_of": forecast["as_of"],
        "start_balance": forecast["start_balance"],
        "proposals": [placement],
    }

    def get(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200, json=board if url.endswith("/proposals") else forecast, request=httpx.Request("GET", url)
        )

    with (
        patch("app.notifications.balance_alerts.httpx.get", side_effect=get),
        patch("app.notifications.balance_alerts.deliver") as deliver,
    ):
        check_accounts(settings, "http://backend", investment_only=True)
        deliver.assert_not_called()

        placement["status"] = "awaiting_approval"
        check_accounts(settings, "http://backend", investment_only=True)
        check_accounts(settings, "http://backend", investment_only=True)

    deliver.assert_called_once()
    notice = deliver.call_args.args[2]
    assert notice.kind == "investment"
    assert notice.amount == "€5,000.00"
