import datetime
import smtplib
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.agents.chat.context import build_business_snapshot
from app.agents.investment.agent import InstrumentRecommendation
from app.agents.investment.service import ProposalService, get_proposal_service
from app.agents.news.client import NewsClient
from app.config import Settings
from app.forecasting.client import Forecast, ForecastClient, get_forecast_client
from app.forecasting.offer_terms import DEFAULT_LOCK_DAYS, OfferTermsClient
from app.main import app
from app.service_client import ServiceClient, ServiceUnavailableError
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

    def fetch_forecast(
        self, account_id: str, horizon_days: int = 90, *, trace_attributes: dict | None = None
    ) -> Forecast:

        return self.forecast


class FakeInstrumentAgentClient:
    configured = True

    def __init__(self, available: bool = True, families: list[dict] | None = None) -> None:
        self.available = available
        self.families = families if families is not None else [DEPOSIT_FAMILY]
        self.calls = 0

    def recommend(self, forecast: Forecast) -> InstrumentRecommendation:
        self.calls += 1
        if not self.available:
            raise ServiceUnavailableError("The instrument agent is not reachable right now.")
        notification = {"subject": "Deposit offers", "body": "Two demo offers."}
        return InstrumentRecommendation.model_validate(
            {"families": self.families, "notification": notification}
        )


def make_variant(offer_id: str, name: str, days: int, rate: float, max_amount: str = "7391.53") -> dict:
    return {
        "offer_id": offer_id,
        "name": name,
        "term_days": days,
        "currency": "EUR",
        "min_amount": "1000.00",
        "max_amount": max_amount,
        "annual_rate_pct": rate,
    }


DEPOSIT_FAMILY = {
    "family_id": "term_deposit",
    "family_name": "Term Deposit",
    "recommended_offer_id": "deposit_30d",
    "reason": "Shortest lockup with a solid rate.",
    "variants": [
        make_variant("deposit_30d", "30-day Term Deposit", 30, 3.5),
        make_variant("deposit_60d", "60-day Term Deposit", 60, 3.8),
    ],
}

BILL_FAMILY = {
    "family_id": "government_bill",
    "family_name": "Government Bill",
    "recommended_offer_id": "government_bill_60d",
    "reason": "Higher amount limit.",
    "variants": [make_variant("government_bill_60d", "60-day Government Bill", 60, 3.2, "5000.00")],
}


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


def test_approval_emails_the_configured_owner_once(
    client: TestClient, repository: DecisionRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipient = "demo-owner@example.org"
    settings = Settings(llm_base_url="http://unused", smtp_host="smtp.example.org",
                        smtp_user="test", smtp_password="unused", owner_email=recipient)
    service = ProposalService(
        settings, FakeForecastClient(make_forecast()), FakeInstrumentAgentClient(), repository
    )
    app.dependency_overrides[get_proposal_service] = lambda: service
    deliver = Mock()
    monkeypatch.setattr("app.agents.investment.service.send_email", deliver)

    path = "/api/proposals/amalfi-deposit_30d-2025-12-31/decision"
    response = client.post(path, json={"decision": "approved"})
    assert response.status_code == 200 and response.json()["notification_status"] == "sent"
    assert client.post(path, json={"decision": "approved"}).status_code == 409
    deliver.assert_called_once()
    assert deliver.call_args.args[1] == recipient
    notifications = client.get("/api/notifications").json()["notifications"]
    assert [(row["status"], row["recipient"]) for row in notifications] == [("sent", "Business owner")]


@pytest.mark.parametrize("copy_refused", [False, True])
def test_approval_sends_one_blind_copy_and_checks_both_recipients(
    client: TestClient, repository: DecisionRepository, monkeypatch: pytest.MonkeyPatch, copy_refused: bool
) -> None:
    owner = "owner@example.org"
    copy = "second@example.org"
    settings = Settings(
        llm_base_url="http://unused", smtp_host="smtp.example.org", smtp_user="sender@example.org",
        smtp_password="unused", owner_email=owner, approval_copy_email=copy,
    )
    family = {
        **DEPOSIT_FAMILY,
        "variants": [make_variant("deposit_30d", "Deposit <Demo> & Co.", 30, 3.5)],
    }
    service = ProposalService(
        settings, FakeForecastClient(make_forecast()), FakeInstrumentAgentClient(families=[family]), repository
    )
    app.dependency_overrides[get_proposal_service] = lambda: service

    # Run smtplib's real envelope and header handling with a local transport.
    smtp = smtplib.SMTP()
    smtp.ehlo_resp = b"ok"
    sendmail = Mock(return_value={copy: (550, b"refused")} if copy_refused else {})
    monkeypatch.setattr(smtp, "sendmail", sendmail)
    monkeypatch.setattr(smtp, "starttls", Mock())
    monkeypatch.setattr(smtp, "login", Mock())
    monkeypatch.setattr(smtplib, "SMTP", Mock(return_value=nullcontext(smtp)))

    path = "/api/proposals/amalfi-deposit_30d-2025-12-31/decision"
    response = client.post(path, json={"decision": "approved"})
    assert response.status_code == 200
    assert response.json()["notification_status"] == ("failed" if copy_refused else "sent")
    assert client.post(path, json={"decision": "approved"}).status_code == 409
    sendmail.assert_called_once()
    sender, envelope, payload = sendmail.call_args.args[:3]
    assert sender == settings.smtp_user and envelope == [owner, copy]
    assert copy.encode() not in payload
    assert owner.encode() in payload
    message = BytesParser(policy=policy.default).parsebytes(payload)
    assert message.get_content_type() == "multipart/alternative"
    plain = message.get_body(("plain",)).get_content()
    html = message.get_body(("html",)).get_content()
    reference = "SIM-" + response.json()["transaction"]["id"][:8].upper()
    for content in (plain, html):
        assert "CFOcus" in content and "Pizzeria Amalfi" in content
        assert "€7,391.53" in content and reference in content
    assert "Deposit <Demo> & Co." in plain
    assert "Deposit &lt;Demo&gt; &amp; Co." in html and "<Demo>" not in html


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
    assert board["warnings"] == ["Investment offers are not available."]


def test_families_become_ranked_proposals_with_a_recommended_term(repository: DecisionRepository) -> None:
    agent = FakeInstrumentAgentClient(families=[DEPOSIT_FAMILY, BILL_FAMILY])
    for client in make_client(repository, make_forecast(), agent):
        proposals = client.get("/api/proposals").json()["proposals"]

    summary = [
        (
            proposal["family_id"],
            proposal["family_rank"],
            proposal["term_days"],
            proposal["is_recommended_term"],
        )
        for proposal in proposals
    ]
    assert summary == [
        ("term_deposit", 1, 30, True),
        ("term_deposit", 1, 60, False),
        ("government_bill", 2, 60, True),
    ]
    bill = proposals[2]
    assert bill["kind"] == "fixed_term_investment"
    assert bill["family_recommendation_reason"] == "Higher amount limit."
    assert bill["interest_eur"] == round(5000 * 0.032 * 60 / 365, 2)
    assert "capped at the offer's maximum of €5,000.00" in bill["rationale"]
    assert {proposal["group"] for proposal in proposals} == {"surplus_placement"}


def test_offer_above_the_forecast_limit_is_rejected(repository: DecisionRepository) -> None:
    too_large = {**BILL_FAMILY, "variants": [make_variant("government_bill_60d", "Bill", 60, 3.2, "9000.00")]}
    for client in make_client(repository, make_forecast(), FakeInstrumentAgentClient(families=[too_large])):
        board = client.get("/api/proposals").json()

    assert board["proposals"] == []
    assert board["warnings"] == ["Investment offers are not available."]


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
    forecast_client = ForecastClient(
        service_client, impact_repository.all_events, 60.0, lambda: (14, 30, 120)
    )
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
    assert forecast_request["lock_days"] == [14, 30]
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


class OfferTermsServiceClient:
    configured = True

    def __init__(self, answer: dict | None) -> None:
        self.answer = answer

    def request_json(self, method: str, path: str, **options) -> dict:
        if self.answer is None:
            raise ServiceUnavailableError("down")
        return self.answer


def test_offer_terms_come_from_the_catalog_and_fall_back_to_defaults() -> None:
    catalog = OfferTermsClient(OfferTermsServiceClient({"term_days": [60, 14, 30, 30]}))
    unavailable = OfferTermsClient(OfferTermsServiceClient(None))

    assert catalog.lock_days() == (14, 30, 60)
    assert unavailable.lock_days() == DEFAULT_LOCK_DAYS


@pytest.mark.parametrize("available", [True, False])
def test_snapshot_traces_forecast_cache_and_news_outcome(
    repository: DecisionRepository, monkeypatch: pytest.MonkeyPatch, available: bool
) -> None:
    forecast_http = Mock(spec=ServiceClient, configured=True)
    news_http = Mock(spec=ServiceClient, configured=True)
    if available:
        forecast_http.request_json.return_value = make_forecast().model_dump()
        news_http.request_json.return_value = {"articles": []}
    else:
        forecast_http.request_json.side_effect = ServiceUnavailableError("upstream failed")
        news_http.request_json.return_value = {}  # An invalid response differs from a valid empty list.
    forecast = ForecastClient(forecast_http, lambda account: [], 10, lambda: (30, 60, 90))
    news = NewsClient(news_http)
    spans: dict[str, dict] = {}
    stack: list[str] = []

    @contextmanager
    def record(name: str) -> Iterator[dict]:
        assert stack == ([] if name == "cfo.business_context" else ["cfo.business_context"])
        stack.append(name)
        spans[name] = {}
        yield spans[name]
        stack.pop()

    monkeypatch.setattr("app.agents.chat.context.trace_span", record)
    status = "ok" if available else "error"
    for cached in (False, True):
        build_business_snapshot("amalfi", forecast, news, repository)
        assert spans["forecast.fetch"]["cache_hit"] is cached
        assert spans["forecast.fetch"]["horizon_days"] == 90
        assert spans["forecast.fetch"]["status"] == status
        assert spans["cfo.business_context"]["forecast_status"] == status
        assert spans["cfo.business_context"]["news_status"] == status
        if available:
            assert spans["news.fetch"] == {"status": "ok", "article_count": 0}
            assert spans["cfo.business_context"]["article_count"] == 0
        else:
            assert spans["news.fetch"] == {"status": "error", "error_type": "ServiceUnavailableError"}
            assert "article_count" not in spans["cfo.business_context"]
    assert forecast_http.request_json.call_count == 1
