import datetime
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents.chat.context import build_business_snapshot
from app.agents.investment.agent import InstrumentRecommendation
from app.agents.investment.service import ProposalService, get_proposal_service
from app.config import Settings
from app.forecasting.client import Forecast, ForecastClient, get_forecast_client
from app.main import app
from app.service_client import ServiceUnavailableError
from app.storage.decisions import DecisionRepository, StoredDecision, get_decision_repository
from app.storage.news_impacts import NewsImpact, NewsImpactRepository, get_news_impact_repository

AS_OF = datetime.date(2025, 12, 31)


def make_forecast(lowest_p5: float = 28788.20) -> Forecast:
    """A forecast shaped like the forecast service's response for the Amalfi account."""
    daily = [
        {
            "date": (AS_OF + datetime.timedelta(days=offset + 1)).isoformat(),
            "p5": lowest_p5 if offset == 9 else 30000.0,
            "p50": 32000.0,
            "p95": 35000.0,
        }
        for offset in range(90)
    ]
    scenario = {
        "buffer": {"amount": 21396.67, "source": "suggested"},
        "safe_to_lock": [
            {"days": 30, "amount": 7391.53, "lowest_balance": 28788.20},
            {"days": 60, "amount": 7391.53, "lowest_balance": 28788.20},
            {"days": 90, "amount": 0.0, "lowest_balance": 15000.0},
        ],
        "p_below_zero": 0.0 if lowest_p5 >= 0 else 0.12,
        "end_balance_p50": 58405.50,
        "daily": daily,
    }
    return Forecast.model_validate(
        {
            "account_id": "amalfi",
            "as_of": AS_OF.isoformat(),
            "start_balance": 33266.35,
            "schedule": [
                {"name": "Main Street Real Estate GmbH", "day": 1, "months": None, "amount": -3800.0}
            ],
            "official": scenario,
            "with_assumptions": scenario,
        }
    )


class FakeForecastClient:
    configured = True

    def __init__(self, forecast: Forecast) -> None:
        self.forecast = forecast

    def fetch_forecast(self, account_id: str, horizon_days: int = 90) -> Forecast:
        return self.forecast


class FakeInstrumentAgentClient:
    configured = True

    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.calls = 0

    def recommend(self, forecast: Forecast) -> InstrumentRecommendation:
        self.calls += 1
        if not self.available:
            raise ServiceUnavailableError("The instrument agent is not reachable right now.")
        offers = [
            {
                "offer_id": f"deposit_{days}d",
                "name": f"Demo {days}-day deposit",
                "term_days": days,
                "currency": "EUR",
                "min_amount": "1000.00",
                "max_amount": "7391.53",
                "annual_rate_pct": rate,
            }
            for days, rate in ((30, 3.5), (60, 3.8))
        ]
        return InstrumentRecommendation.model_validate(
            {"offers": offers, "notification": {"subject": "Deposit offers", "body": "Two demo offers."}}
        )


class FakeNewsClient:
    configured = True

    def fetch_relevant_articles(self, limit: int = 10) -> list:
        raise ServiceUnavailableError("down")


@pytest.fixture
def repository(tmp_path: Path) -> DecisionRepository:
    return DecisionRepository(tmp_path / "decisions.sqlite3")


def make_client(
    repository: DecisionRepository, forecast: Forecast, instrument_agent: FakeInstrumentAgentClient
) -> Iterator[TestClient]:
    service = ProposalService(
        Settings(llm_base_url="http://unused/v1"), FakeForecastClient(forecast), instrument_agent, repository
    )
    app.dependency_overrides[get_proposal_service] = lambda: service
    app.dependency_overrides[get_decision_repository] = lambda: repository
    try:
        yield TestClient(app, headers={"X-Account-Id": "amalfi"})
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def instrument_agent() -> FakeInstrumentAgentClient:
    return FakeInstrumentAgentClient()


@pytest.fixture
def client(
    repository: DecisionRepository, instrument_agent: FakeInstrumentAgentClient
) -> Iterator[TestClient]:
    yield from make_client(repository, make_forecast(), instrument_agent)


def test_proposals_explain_deposit_offers(client: TestClient) -> None:
    board = client.get("/api/proposals").json()

    assert [proposal["id"] for proposal in board["proposals"]] == [
        "amalfi-deposit_30d-2025-12-31",
        "amalfi-deposit_60d-2025-12-31",
    ]
    proposal = board["proposals"][0]
    assert proposal["status"] == "awaiting_approval"
    assert proposal["requires_approval"] is True
    assert proposal["execution_mode"] == "simulated"
    assert "€28,788.20 − buffer €21,396.67 = €7,391.53" in proposal["rationale"]
    assert board["notification_draft"]["subject"] == "Deposit offers"


def test_instrument_agent_answer_is_cached(
    client: TestClient, instrument_agent: FakeInstrumentAgentClient
) -> None:
    client.get("/api/proposals")
    client.get("/api/proposals")

    assert instrument_agent.calls == 1


def test_approval_records_transaction_and_supersedes_alternatives(client: TestClient) -> None:
    response = client.post(
        "/api/proposals/amalfi-deposit_30d-2025-12-31/decision", json={"decision": "approved"}
    )

    assert response.status_code == 200
    assert response.json()["transaction"]["amount"] == 7391.53
    assert response.json()["notification_status"] == "queued"
    statuses = {
        proposal["id"]: proposal["status"] for proposal in client.get("/api/proposals").json()["proposals"]
    }
    assert statuses == {
        "amalfi-deposit_30d-2025-12-31": "approved",
        "amalfi-deposit_60d-2025-12-31": "superseded",
    }
    assert len(client.get("/api/transactions").json()["transactions"]) == 1
    notification = client.get("/api/notifications").json()["notifications"][0]
    assert notification["subject"].startswith("Approved (simulated)")

    second = client.post(
        "/api/proposals/amalfi-deposit_60d-2025-12-31/decision", json={"decision": "approved"}
    )
    assert second.status_code == 409


def test_decline_records_no_transaction(client: TestClient) -> None:
    response = client.post(
        "/api/proposals/amalfi-deposit_30d-2025-12-31/decision", json={"decision": "declined"}
    )

    assert response.json()["transaction"] is None
    assert client.get("/api/transactions").json()["transactions"] == []


def test_unknown_proposal_is_404(client: TestClient) -> None:
    response = client.post("/api/proposals/nope/decision", json={"decision": "approved"})

    assert response.status_code == 404


def test_credit_line_proposed_when_balance_may_go_negative(repository: DecisionRepository) -> None:
    for client in make_client(
        repository, make_forecast(lowest_p5=-22097.60), FakeInstrumentAgentClient(False)
    ):
        board = client.get("/api/proposals").json()

    credit_line = board["proposals"][0]
    assert credit_line["kind"] == "credit_line"
    assert credit_line["amount"] == 23000
    assert "−€22,097.60" in credit_line["analysis"]
    assert board["warnings"] == [
        "Deposit offers are not available: The instrument agent is not reachable right now."
    ]


def test_business_snapshot_contains_forecast_and_skips_unavailable_news(
    repository: DecisionRepository,
) -> None:
    snapshot = build_business_snapshot(
        "amalfi", FakeForecastClient(make_forecast()), FakeNewsClient(), repository
    )

    assert "€33,266.35" in snapshot
    assert "30 days €7,391.53" in snapshot
    assert "Main Street Real Estate GmbH −€3,800.00 on day 1" in snapshot
    assert "news" not in snapshot.lower()


ENERGY_EVENT = {
    "type": "shift_amount",
    "stream": "City Energy & Utilities AG",
    "from": "2026-02-01",
    "change_pct": 15.0,
    "certainty": "official",
    "why": "supplier letter: tariff +15% from 1 Feb",
}


class RecordingServiceClient:
    """Stands in for the forecast service and records what the backend sent."""

    configured = True

    def __init__(self) -> None:
        self.requests: list[tuple[str, dict]] = []

    def request_json(self, method: str, path: str, timeout_seconds: float | None = None, **options) -> dict:
        self.requests.append((path, options.get("json", {})))
        if path == "/news/events":
            return {
                "account_id": "amalfi",
                "events": [ENERGY_EVENT],
                "rejected": [{"event": {}, "reason": "x"}],
            }
        return make_forecast().model_dump(mode="json")


def test_applied_news_events_are_sent_with_the_forecast(tmp_path: Path) -> None:
    impact_repository = NewsImpactRepository(tmp_path / "impacts.sqlite3")
    service_client = RecordingServiceClient()
    forecast_client = ForecastClient(service_client, impact_repository.all_events, 60.0)
    app.dependency_overrides[get_forecast_client] = lambda: forecast_client
    app.dependency_overrides[get_news_impact_repository] = lambda: impact_repository
    try:
        client = TestClient(app, headers={"X-Account-Id": "amalfi"})
        applied = client.post(
            "/api/news/impacts",
            json={"article_id": "abc123def456", "title": "Energy prices rise", "summary": "Tariff +15 %"},
        ).json()
        impacts = client.get("/api/news/impacts").json()["impacts"]
        forecast_client.fetch_forecast("amalfi")
        removed = client.delete("/api/news/impacts/abc123def456")
        missing = client.delete("/api/news/impacts/abc123def456")
    finally:
        app.dependency_overrides.clear()

    assert applied["events"] == [ENERGY_EVENT]
    assert applied["rejected_count"] == 1
    assert [impact["article_id"] for impact in impacts] == ["abc123def456"]
    forecast_request = next(body for path, body in service_client.requests if path == "/forecast")
    assert forecast_request["events"] == [ENERGY_EVENT]
    assert removed.status_code == 204
    assert missing.status_code == 404
    assert impact_repository.all_events("amalfi") == []


def test_deposit_proposal_shows_offer_range_and_interest(client: TestClient) -> None:
    proposal = client.get("/api/proposals").json()["proposals"][0]

    assert proposal["min_amount"] == 1000.0
    assert proposal["lowest_balance"] == 28788.20
    assert proposal["buffer_eur"] == 21396.67
    assert proposal["safe_amount"] == 7391.53
    assert proposal["interest_eur"] == round(7391.53 * 0.035 * 30 / 365, 2)


def test_requests_without_a_known_account_are_refused(client: TestClient) -> None:
    anonymous = TestClient(app)

    assert anonymous.get("/api/proposals").status_code == 401
    assert anonymous.get("/api/proposals", headers={"X-Account-Id": "someone-else"}).status_code == 403


def test_each_account_only_sees_its_own_records(tmp_path: Path) -> None:
    repository = DecisionRepository(tmp_path / "decisions.sqlite3")
    impacts = NewsImpactRepository(tmp_path / "impacts.sqlite3")
    decision = StoredDecision(
        proposal_id="amalfi-deposit_30d-2025-12-31",
        proposal_group="surplus_placement",
        decision="declined",
        title="Deposit",
        amount=1.0,
        decided_at="2026-01-01T00:00:00Z",
    )
    repository.record_decision("amalfi", decision, None, None)
    impact = NewsImpact(
        article_id="abc123def456", title="News", events=[ENERGY_EVENT], rejected_count=0, created_at="x"
    )
    impacts.save_impact("amalfi", impact)
    impacts.save_impact("bakery", impact.model_copy(update={"events": []}))

    assert list(repository.list_decisions("amalfi")) == ["amalfi-deposit_30d-2025-12-31"]
    assert repository.list_decisions("bakery") == {}
    assert impacts.all_events("amalfi") == [ENERGY_EVENT]
    assert impacts.all_events("bakery") == []


def test_approval_from_an_older_board_does_not_block_new_proposals(
    repository: DecisionRepository, client: TestClient
) -> None:
    old_approval = StoredDecision(
        proposal_id="amalfi-deposit_30d-2025-06-30",
        proposal_group="surplus_placement",
        decision="approved",
        title="Old deposit",
        amount=1.0,
        decided_at="2025-07-01T00:00:00Z",
    )
    repository.record_decision("amalfi", old_approval, None, None)

    statuses = {proposal["status"] for proposal in client.get("/api/proposals").json()["proposals"]}

    assert statuses == {"awaiting_approval"}
