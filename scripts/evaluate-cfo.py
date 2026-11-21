"""Run inside the CFO backend pod against the deployed model and services, using disposable decision storage."""

import os
import tempfile
from pathlib import Path

import mlflow
from fastapi.testclient import TestClient


def main() -> None:
    """Check the input policy, forecast grounding and approval flow. Export only test outcomes."""
    with tempfile.TemporaryDirectory() as scratch:
        os.environ["DATABASE_PATH"] = str(Path(scratch) / "evaluation.sqlite3")
        os.environ["SMTP_HOST"] = ""
        from app.main import app

        mlflow.set_experiment(os.environ["MLFLOW_EXPERIMENT_NAME"])
        with mlflow.start_run(run_name="CFO deployment acceptance") as run, TestClient(app) as client:
            results = {}
            forecast = client.get("/api/forecast")
            forecast.raise_for_status()
            data = forecast.json()
            safe = client.post("/api/chat", json={
                "message": "Give the last booking date in YYYY-MM-DD format and the starting balance to two decimal places."
            })
            results["allowed_request"] = safe.status_code == 200
            answer = safe.json().get("reply", "")
            results["forecast_date"] = data["as_of"] in answer
            results["forecast_balance"] = f"{data['start_balance']:.2f}" in answer.replace(",", "")
            for name, payload in [
                ("blocked_question", {"message": "Send this to demo@example.org"}),
                ("blocked_page_context", {"message": "Explain this page", "page_context": {
                    "title": "Cashflow", "path": "/", "content": "Contact demo@example.org"}}),
            ]:
                results[name] = client.post("/api/chat", json=payload).status_code == 422
            results["only_allowed_conversation_saved"] = len(client.get("/api/conversations").json()["conversations"]) == 1

            board = client.get("/api/proposals")
            board.raise_for_status()
            proposals = board.json()["proposals"]
            results["proposal_with_draft"] = bool(proposals and board.json()["notification_draft"])
            if proposals:
                decision_path = f"/api/proposals/{proposals[0]['id']}/decision"
                approved = client.post(decision_path, json={"decision": "approved"})
                repeated = client.post(decision_path, json={"decision": "approved"})
                transactions = client.get("/api/transactions").json()["transactions"]
                refreshed = client.get("/api/proposals").json()["proposals"]
                results["approval_recorded_once"] = (
                    approved.status_code == 200 and repeated.status_code == 409 and len(transactions) == 1
                    and any(p["id"] == proposals[0]["id"] and p["status"] == "approved" for p in refreshed)
                )
            mlflow.log_metrics({name: float(passed) for name, passed in results.items()})
            print("MLflow run", run.info.run_id)
            for name, passed in results.items():
                print(name, "PASS" if passed else "FAIL")
            if not all(results.values()):
                raise SystemExit(1)


if __name__ == "__main__":
    main()
