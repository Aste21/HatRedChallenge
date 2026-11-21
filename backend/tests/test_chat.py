import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError

from app.agents.chat.agent import CHART_FAILED_REPLY, TITLE_PROMPT, _clean_title
from app.agents.chat.charts import describe_chart, parse_chart_arguments
from app.agents.chat.context import get_business_snapshot
from app.knowledge import load_company_knowledge
from app.llm import LlmReply, ToolCall, get_llm_client
from app.main import app
from app.storage.conversations import ConversationRepository, get_conversation_repository


class FakeLlmClient:
    """Records every request; answers title requests with a canned title and chat requests with a reply.

    `chart_arguments` makes the chat requests call the chart tool, one entry per attempt.
    """

    def __init__(
        self,
        title: str = "Summer cash dip",
        fail_titles: bool = False,
        chart_arguments: list[str] | None = None,
    ) -> None:
        self.requests: list[list[dict[str, Any]]] = []
        self.title = title
        self.fail_titles = fail_titles
        self.chart_arguments = list(chart_arguments or [])

    def complete(
        self, messages: list[dict[str, Any]], temperature: float = 0.2, max_tokens: int | None = None
    ) -> str:
        self.requests.append(messages)
        if max_tokens is not None:
            if self.fail_titles:
                raise APIConnectionError(request=None)  # type: ignore[arg-type]
            return self.title
        if messages[-1]["role"] == "tool":
            return "Here are your monthly receipts."
        return "Ciao Vincenzo!"

    def complete_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], temperature: float = 0.2
    ) -> LlmReply:
        self.requests.append(messages)
        if self.chart_arguments:
            arguments = self.chart_arguments.pop(0)
            return LlmReply(
                content="", tool_calls=[ToolCall(id="call-1", name="create_chart", arguments=arguments)]
            )
        return LlmReply(content="Ciao Vincenzo!", tool_calls=[])

    @property
    def chat_requests(self) -> list[list[dict[str, Any]]]:
        return [messages for messages in self.requests if messages[0]["content"] != TITLE_PROMPT]


@pytest.fixture
def fake_llm_client() -> FakeLlmClient:
    return FakeLlmClient()


@pytest.fixture
def client(tmp_path: Path, fake_llm_client: FakeLlmClient) -> Iterator[TestClient]:
    repository = ConversationRepository(tmp_path / "chat.sqlite3")
    app.dependency_overrides[get_llm_client] = lambda: fake_llm_client
    app.dependency_overrides[get_conversation_repository] = lambda: repository
    app.dependency_overrides[get_business_snapshot] = lambda: ""
    try:
        yield TestClient(app, headers={"X-Account-Id": "amalfi"})
    finally:
        app.dependency_overrides.clear()


def test_first_message_creates_titled_conversation(
    client: TestClient, fake_llm_client: FakeLlmClient
) -> None:
    response = client.post("/api/chat", json={"message": "Why did cash fall in summer?"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Ciao Vincenzo!"
    assert body["title"] == "Summer cash dip"
    chat_messages = fake_llm_client.chat_requests[0]
    assert chat_messages[0]["role"] == "system"
    assert chat_messages[-1] == {"role": "user", "content": "Why did cash fall in summer?"}

    stored = client.get(f"/api/conversations/{body['conversation_id']}").json()
    assert [message["role"] for message in stored["messages"]] == ["user", "assistant"]
    assert client.get("/api/conversations").json()["conversations"][0]["title"] == "Summer cash dip"


def test_follow_up_uses_stored_history_and_keeps_title(
    client: TestClient, fake_llm_client: FakeLlmClient
) -> None:
    conversation_id = client.post("/api/chat", json={"message": "Hi"}).json()["conversation_id"]
    response = client.post("/api/chat", json={"conversation_id": conversation_id, "message": "And now?"})

    assert response.json()["title"] == "Summer cash dip"
    assert len(fake_llm_client.requests) == 3  # chat + title, then chat only
    assert [message["content"] for message in fake_llm_client.chat_requests[1][1:]] == [
        "Hi",
        "Ciao Vincenzo!",
        "And now?",
    ]


def test_page_context_is_added_to_system_prompt(client: TestClient, fake_llm_client: FakeLlmClient) -> None:
    page_context = {"path": "/", "title": "Cashflow", "content": "Closing balance €33,266.34"}
    client.post("/api/chat", json={"message": "What is this?", "page_context": page_context})

    system_prompt = fake_llm_client.chat_requests[0][0]["content"]
    assert "'Cashflow' page" in system_prompt
    assert "Closing balance €33,266.34" in system_prompt


def test_title_falls_back_to_question_when_llm_fails(client: TestClient) -> None:
    app.dependency_overrides[get_llm_client] = lambda: FakeLlmClient(fail_titles=True)
    response = client.post("/api/chat", json={"message": "Which bills are due next month?"})

    assert response.json()["title"] == "Which bills are due next month?"


def test_unknown_conversation_returns_404(client: TestClient) -> None:
    assert client.post("/api/chat", json={"conversation_id": "missing", "message": "Hi"}).status_code == 404
    assert client.get("/api/conversations/missing").status_code == 404


def test_blank_message_is_rejected(client: TestClient) -> None:
    assert client.post("/api/chat", json={"message": "   "}).status_code == 422


def test_delete_conversation(client: TestClient) -> None:
    conversation_id = client.post("/api/chat", json={"message": "Hi"}).json()["conversation_id"]

    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 204
    assert client.get("/api/conversations").json() == {"conversations": []}


MONTHLY_RECEIPTS_CHART = json.dumps(
    {"title": "Receipts per month", "metrics": ["money_in"], "chart_type": "bar", "granularity": "month"}
)


def test_chart_request_returns_and_stores_chart(client: TestClient) -> None:
    app.dependency_overrides[get_llm_client] = lambda: FakeLlmClient(chart_arguments=[MONTHLY_RECEIPTS_CHART])
    body = client.post("/api/chat", json={"message": "Chart my receipts per month"}).json()

    assert body["reply"] == "Here are your monthly receipts."
    assert body["chart"]["title"] == "Receipts per month"
    assert body["chart"]["metrics"] == ["money_in"]
    stored = client.get(f"/api/conversations/{body['conversation_id']}").json()
    assert stored["messages"][0]["chart"] is None
    assert stored["messages"][1]["chart"] == body["chart"]


def test_chart_is_described_in_follow_up_history(client: TestClient) -> None:
    fake_llm_client = FakeLlmClient(chart_arguments=[MONTHLY_RECEIPTS_CHART])
    app.dependency_overrides[get_llm_client] = lambda: fake_llm_client
    first_reply = client.post("/api/chat", json={"message": "Chart my receipts"}).json()
    conversation_id = first_reply["conversation_id"]
    client.post("/api/chat", json={"conversation_id": conversation_id, "message": "Now as a line"})

    previous_reply = fake_llm_client.chat_requests[-1][2]["content"]
    assert '(Chart shown: "Receipts per month" (money in; bar; per month))' in previous_reply


def test_invalid_chart_is_retried_once(client: TestClient) -> None:
    app.dependency_overrides[get_llm_client] = lambda: FakeLlmClient(
        chart_arguments=['{"title": "Bad"}', MONTHLY_RECEIPTS_CHART]
    )
    body = client.post("/api/chat", json={"message": "Chart my receipts"}).json()

    assert body["chart"]["title"] == "Receipts per month"


def test_invalid_chart_twice_falls_back_to_fixed_message(client: TestClient) -> None:
    app.dependency_overrides[get_llm_client] = lambda: FakeLlmClient(
        chart_arguments=["not json", '{"metrics": ["profit"]}']
    )
    body = client.post("/api/chat", json={"message": "Chart my receipts"}).json()

    assert body["reply"] == CHART_FAILED_REPLY
    assert body["chart"] is None


def test_chart_arguments_are_normalised() -> None:
    chart = parse_chart_arguments(
        json.dumps(
            {
                "title": "Costs",
                "metrics": ["money_out", "spending_by_category"],
                "chart_type": "line",
                "start_month": "2025-09",
                "end_month": "2025-03",
            }
        )
    )

    assert chart is not None
    assert chart.metrics == ["spending_by_category"]
    assert chart.chart_type == "bar"
    # The category totals always cover the whole statement, so months are dropped.
    assert (chart.start_month, chart.end_month) == (None, None)
    assert parse_chart_arguments('{"title": "X", "metrics": "balance"}').metrics == ["balance"]


def test_payroll_metrics_are_accepted() -> None:
    chart = parse_chart_arguments(
        json.dumps(
            {
                "title": "Payroll",
                "metrics": ["payroll", "money_out"],
                "chart_type": "line",
                "granularity": "month",
            }
        )
    )

    assert chart is not None
    assert chart.metrics == ["payroll", "money_out"]
    assert chart.chart_type == "line"
    assert describe_chart(chart) == '"Payroll" (net payroll, money out; line; per month)'


def test_payroll_breakdown_keeps_ordered_months() -> None:
    chart = parse_chart_arguments(
        json.dumps(
            {
                "title": "Pay per person",
                "metrics": ["payroll", "payroll_by_employee"],
                "chart_type": "area",
                "start_month": "2025-09",
                "end_month": "2025-03",
            }
        )
    )

    assert chart is not None
    assert chart.metrics == ["payroll_by_employee"]
    assert chart.chart_type == "bar"
    assert (chart.start_month, chart.end_month) == ("2025-03", "2025-09")
    assert describe_chart(chart) == '"Pay per person" (total net pay per employee; bar; 2025-03 to 2025-09)'


def test_unsupported_chart_options_fall_back_to_defaults() -> None:
    chart = parse_chart_arguments(
        json.dumps(
            {
                "title": "Where the money goes",
                "metrics": ["profit", "money_out"],
                "chart_type": "pie",
                "granularity": "quarter",
                "start_month": "2025-03-01",
                "end_month": "June",
            }
        )
    )

    assert chart is not None
    assert chart.metrics == ["money_out"]
    assert (chart.chart_type, chart.granularity) == ("bar", "month")
    assert (chart.start_month, chart.end_month) == ("2025-03", None)


def test_company_knowledge_is_added_to_system_prompt(
    client: TestClient, fake_llm_client: FakeLlmClient
) -> None:
    client.post("/api/chat", json={"message": "Who works here?"})

    system_prompt = fake_llm_client.chat_requests[0][0]["content"]
    assert system_prompt.startswith("You are CFOcus, the AI CFO assistant of Pizzeria Amalfi")
    knowledge = system_prompt.split("<company_knowledge>\n", 1)[1].split("\n</company_knowledge>", 1)[0]
    assert knowledge == load_company_knowledge("amalfi")
    assert "Yusuf Akcit" in knowledge
    assert "4,166.67 CHF" in knowledge


def test_company_knowledge_is_per_account() -> None:
    assert len(load_company_knowledge("amalfi")) < 4000
    assert load_company_knowledge("unknown-account") == ""
    assert load_company_knowledge("../amalfi") == ""


def test_statement_period_is_added_to_system_prompt(
    client: TestClient, fake_llm_client: FakeLlmClient
) -> None:
    statement_period = {"first_day": "2025-01-01", "last_day": "2025-12-31"}
    client.post("/api/chat", json={"message": "Chart June", "statement_period": statement_period})

    assert "covers 2025-01-01 to 2025-12-31" in fake_llm_client.chat_requests[0][0]["content"]


@pytest.mark.parametrize(
    ("raw_title", "expected_title"),
    [
        ('"Summer Cash Dip."', "Summer Cash Dip"),
        ("Title: **Monthly bills**\nExtra line", "Monthly bills"),
        ("   ", ""),
    ],
)
def test_clean_title(raw_title: str, expected_title: str) -> None:
    assert _clean_title(raw_title) == expected_title


def test_statement_summary_is_added_to_business_data(
    client: TestClient, fake_llm_client: FakeLlmClient
) -> None:
    summary = "June: €0.00 / €22,105.00 / -€22,105.00 / -€20,098.69"
    client.post("/api/chat", json={"message": "What happened in June?", "statement_summary": summary})

    system_prompt = fake_llm_client.chat_requests[0][0]["content"]
    assert f"<data>\n{summary}\n</data>" in system_prompt
