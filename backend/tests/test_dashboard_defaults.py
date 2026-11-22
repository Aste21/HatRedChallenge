from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dashboard_defaults import router
from app.config import Settings, get_settings


def test_first_saved_dashboard_becomes_the_account_default(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(router)
    settings = Settings(llm_base_url="http://llm", database_path=tmp_path / "cfo.sqlite3")
    app.dependency_overrides[get_settings] = lambda: settings
    url = "/api/dashboard-defaults"
    chart = {
        "id": "balance",
        "span": 8,
        "spec": {"title": "Monthly balance", "metrics": ["balance"]},
    }

    with TestClient(app) as client:
        assert client.get(url).status_code == 401
        client.headers["X-Account-Id"] = "amalfi"
        assert client.get(url).json() == {"charts": []}
        assert client.put(url, json={"charts": []}).status_code == 204
        assert client.put(url, json={"charts": [chart]}).status_code == 204
        assert client.put(url, json={"charts": [{**chart, "span": 12}]}).status_code == 204

    with TestClient(app, headers={"X-Account-Id": "amalfi"}) as fresh_client:
        saved = fresh_client.get(url).json()["charts"]
        assert [(entry["id"], entry["span"], entry["spec"]["title"]) for entry in saved] == [
            ("balance", 8, "Monthly balance")
        ]
        edited = {**chart, "span": 12}
        assert fresh_client.post(url, json={"charts": [edited]}).status_code == 204

    with TestClient(app, headers={"X-Account-Id": "amalfi"}) as next_session:
        assert next_session.get(url).json()["charts"][0]["span"] == 12
