"""End-to-end tests of the API on the demo account. Run with:  pytest -q

The LLM is replaced by a stub, so the tests run without a model endpoint.
"""
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings

DEMO_DATA = Path(__file__).resolve().parents[1] / "data"
STATEMENT = (DEMO_DATA / "accounts" / "amalfi" / "statement.csv").read_bytes()

DEMO_EVENTS = [   # what the news model is expected to return for the notebook's demo news
    {"type": "shift_amount", "stream": "Tax Office Frankfurt am Main #3", "from": "2026-02-15", "change_pct": 8, "certainty": "official"},
    {"type": "shift_amount", "stream": "City Energy & Utilities AG", "from": "2026-02-01", "change_pct": 15, "certainty": "official"},
    {"type": "one_off", "date": "2026-01-20", "amount": -1200, "certainty": "official"},
    {"type": "scale", "flow": "sales", "from": "2026-01-01", "factor_mean": 0.95, "factor_sd": 0.04, "certainty": "assumption"},
    {"type": "scale", "flow": "sales", "from": "2026-01-12", "to": "2026-01-25", "factor_mean": 0.6, "factor_sd": 0.1, "certainty": "assumption"},
]


def make_settings(data_dir, llm=True):
    return Settings(llm_base_url="http://llm.test/v1" if llm else "", llm_api_key="secret", llm_model="test-model",
                    llm_verify_tls=True, llm_timeout_s=5, llm_max_tokens=500, llm_json_mode=True, data_dir=str(data_dir))


@pytest.fixture
def client(tmp_path):
    """API client working on a private copy of the demo data."""
    shutil.copytree(DEMO_DATA, tmp_path / "data")
    main.app.dependency_overrides[main.get_settings] = lambda: make_settings(tmp_path / "data")
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def forecast(client, **body):
    r = client.post("/forecast", json={"account_id": "amalfi", **body})
    assert r.status_code == 200, r.text
    return r.json()


# --- forecast ------------------------------------------------------------------------------------------

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_schedule_is_detected_from_the_statement(client):
    sched = {p["name"]: p for p in forecast(client)["schedule"]}
    assert len(sched) == 11                                   # rent, energy, 3 tax, wire, social security, 4 salaries
    assert sched["Main Street Real Estate GmbH"]["day"] == 1
    assert sched["Main Street Real Estate GmbH"]["amount"] == -3800
    assert sched["Tax Office Frankfurt am Main"]["months"] == [3, 6, 9, 12]   # quarterly income tax


def test_baseline_matches_the_notebook(client):
    j = forecast(client)
    assert j["as_of"] == "2025-12-31" and j["start_balance"] == 33266.35
    s = j["official"]
    assert len(s["daily"]) == 90
    assert 21_000 < s["buffer"]["amount"] < 22_000 and s["buffer"]["source"] == "suggested"
    assert [x["days"] for x in s["safe_to_lock"]] == [30, 60, 90]
    assert 7_000 < s["safe_to_lock"][0]["amount"] < 8_000    # notebook: 7,403 EUR
    assert j["official"] == j["with_assumptions"]             # no events -> identical scenarios


def test_official_and_assumption_events_are_split(client):
    j = forecast(client, events=DEMO_EVENTS)
    assert len(j["official"]["events"]) == 3
    assert len(j["with_assumptions"]["events"]) == 5
    assert j["with_assumptions"]["end_balance_p50"] < j["official"]["end_balance_p50"]
    assert j["with_assumptions"]["safe_to_lock"][0]["amount"] == 0   # road works + weak demand eat the room


def test_user_buffer_replaces_the_suggested_one(client):
    suggested = forecast(client)["official"]
    zero = forecast(client, buffer_eur=0)["official"]
    assert zero["buffer"] == {"amount": 0, "source": "user"}
    assert zero["safe_to_lock"][0]["amount"] == pytest.approx(
        suggested["safe_to_lock"][0]["amount"] + suggested["buffer"]["amount"], abs=0.02)


def test_current_balance_overrides_the_stored_one(client):
    assert forecast(client, current_balance=50_000)["start_balance"] == 50_000


@pytest.mark.parametrize("body", [
    {"events": [{"type": "shift_amount", "stream": "VAT", "from": "2026-02-01", "change_pct": 5}]},
    {"events": [{"type": "scale", "flow": "sales", "from": "2026-01-01", "factor_mean": 0.2, "factor_sd": 0}]},
    {"events": [{"type": "closure", "from": "2026-02-01", "to": "2026-01-01"}]},
    {"horizon": 30, "lock_days": [60]},
])
def test_bad_requests_are_rejected(client, body):
    assert client.post("/forecast", json={"account_id": "amalfi", **body}).status_code == 422


def test_unknown_or_unsafe_account_ids(client):
    assert client.post("/forecast", json={"account_id": "nobody"}).status_code == 404
    assert client.post("/forecast", json={"account_id": "../etc"}).status_code == 422


# --- upload --------------------------------------------------------------------------------------------

def test_upload_creates_a_new_account(client):
    r = client.put("/accounts/bakery/statement?closing_balance=12000&description=Bakery", content=STATEMENT,
                   headers={"Content-Type": "text/csv"})
    assert r.status_code == 200, r.text
    assert r.json() == {"account_id": "bakery", "transactions": 1125, "first_date": "2025-01-01",
                        "last_date": "2025-12-31", "closing_balance": 12000}
    j = client.post("/forecast", json={"account_id": "bakery"}).json()
    assert j["start_balance"] == 12000


def test_upload_rejects_a_file_that_is_not_a_statement(client):
    r = client.put("/accounts/bakery/statement?closing_balance=1", content=b"a;b\n1;2\n")
    assert r.status_code == 400 and "missing columns" in r.json()["detail"]


# --- news ----------------------------------------------------------------------------------------------

def test_news_returns_checked_events(client, monkeypatch):
    reply = """```json
    {"events": [
      {"type": "shift_amount", "stream": "City Energy & Utilities AG", "from": "2026-02-01", "change_pct": 15, "certainty": "official", "why": "tariff letter"},
      {"type": "scale", "flow": "sales", "from": "2026-01-01", "factor_mean": 0.2, "factor_sd": 0},
      {"type": "shift_amount", "stream": "VAT", "from": "2026-02-01", "change_pct": 5}
    ]}
    ```"""
    seen = {}

    def fake_llm(settings, news, context):
        seen["context"] = context
        return reply

    monkeypatch.setattr(main, "ask_llm", fake_llm)
    r = client.post("/news/events", json={"account_id": "amalfi", "news": "Energy tariff +15% from 1 Feb 2026"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert [e["stream"] for e in j["events"]] == ["City Energy & Utilities AG"]
    assert len(j["rejected"]) == 2 and "unknown scheduled payment" in j["rejected"][1]["reason"]
    assert '"City Energy & Utilities AG": day 10' in seen["context"]       # the model sees this account's payments
    # the accepted events can be sent straight to /forecast
    assert forecast(client, events=j["events"])["official"]["events"] == j["events"]


def test_news_sends_an_openai_compatible_request(client, monkeypatch):
    sent = {}

    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": '{"events": []}'}}]}

    def fake_post(url, json, headers, timeout, verify):
        sent.update(url=url, body=json, headers=headers)
        return FakeResponse()

    monkeypatch.setattr("app.news.httpx.post", fake_post)
    r = client.post("/news/events", json={"account_id": "amalfi", "news": "Local football club wins the cup."})
    assert r.json()["events"] == []
    assert sent["url"] == "http://llm.test/v1/chat/completions"
    assert sent["headers"] == {"Authorization": "Bearer secret"}
    assert sent["body"]["model"] == "test-model" and sent["body"]["response_format"] == {"type": "json_object"}


def test_news_errors(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "ask_llm", lambda *a: "Sorry, I cannot help with that.")
    assert client.post("/news/events", json={"account_id": "amalfi", "news": "x"}).status_code == 502

    main.app.dependency_overrides[main.get_settings] = lambda: make_settings(tmp_path / "data", llm=False)
    assert client.post("/news/events", json={"account_id": "amalfi", "news": "x"}).status_code == 503
