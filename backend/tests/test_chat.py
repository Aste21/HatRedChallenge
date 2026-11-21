from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError

from app.agents.chat.agent import TITLE_PROMPT, _clean_title
from app.agents.chat.context import get_business_snapshot
from app.llm import get_llm_client
from app.main import app
from app.storage.conversations import ConversationRepository, get_conversation_repository


class FakeLlmClient:
    """Records every request; answers title requests with a canned title and chat requests with a reply."""

    def __init__(self, title: str = "Summer cash dip", fail_titles: bool = False) -> None:
        self.requests: list[list[dict[str, str]]] = []
        self.title = title
        self.fail_titles = fail_titles

    def complete(
        self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int | None = None
    ) -> str:
        self.requests.append(messages)
        if max_tokens is not None:
            if self.fail_titles:
                raise APIConnectionError(request=None)  # type: ignore[arg-type]
            return self.title
        return "Ciao Vincenzo!"

    @property
    def chat_requests(self) -> list[list[dict[str, str]]]:
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
        yield TestClient(app)
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
