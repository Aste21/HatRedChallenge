import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from pydantic import BaseModel, Field

from app.accounts import AccountProfile, get_account
from app.agents.chat.agent import ChatMessage, PageContext, answer, generate_title
from app.agents.chat.charts import ChartSpec, StatementPeriod
from app.agents.chat.context import get_business_snapshot
from app.llm import LlmClient, get_llm_client
from app.storage.conversations import (
    ConversationRepository,
    ConversationSummary,
    get_conversation_repository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_STATEMENT_SUMMARY_CHARACTERS = 4000


class ChatRequest(BaseModel):
    """A new user message; the history is loaded from storage by `conversation_id`.

    `statement_period` and `statement_summary` are set by the frontend server, which holds the account's
    bank statement and computes its figures.
    """

    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    page_context: PageContext | None = None
    statement_period: StatementPeriod | None = None
    statement_summary: str = Field(default="", max_length=MAX_STATEMENT_SUMMARY_CHARACTERS)


class ChatResponse(BaseModel):
    """The assistant's reply plus the conversation it was stored in and the chart it shows, if any."""

    conversation_id: str
    title: str
    reply: str
    chart: ChartSpec | None = None


@router.post("", response_model=ChatResponse)
def post_chat(
    request: ChatRequest,
    account: Annotated[AccountProfile, Depends(get_account)],
    llm_client: Annotated[LlmClient, Depends(get_llm_client)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    business_snapshot: Annotated[str, Depends(get_business_snapshot)],
) -> ChatResponse:
    """Answer a user message and store the exchange in the chat history.

    Args:
        request: The new message, the optional conversation it belongs to and the visible page content.
        account: The signed-in account.
        llm_client: Injected LLM client.
        repository: Injected chat history store.
        business_snapshot: Latest forecast, approved actions and news, for answers with real numbers.

    Returns:
        The assistant reply with the conversation id and title.

    Steps:
        1. Load the existing conversation (404 if the id is unknown) or start with an empty history.
        2. Ask the chat agent for a reply; map LLM failures to HTTP 502 without storing anything,
           so the UI can simply retry.
        3. For a new conversation, generate its title from the first message and create it.
        4. Store the question and the reply together.
        The bank-statement figures from the frontend come first in the business data, before the forecast.
    """
    question = request.message.strip()
    if not question:
        raise HTTPException(status_code=422, detail="The message must not be empty.")
    conversation: ConversationSummary | None = None
    history: list[ChatMessage] = []
    if request.conversation_id is not None:
        conversation = repository.get_conversation(account.id, request.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="This conversation no longer exists.")
        history = [
            ChatMessage(role=message.role, content=message.content, chart=message.chart)
            for message in conversation.messages
        ]
    history.append(ChatMessage(role="user", content=question))

    business_data = "\n".join(part for part in (request.statement_summary.strip(), business_snapshot) if part)
    try:
        chat_answer = answer(
            llm_client, history, request.page_context, business_data, account, request.statement_period
        )
    except OpenAIError as error:
        logger.exception("LLM call failed")
        raise HTTPException(
            status_code=502, detail="The language model is not reachable right now."
        ) from error
    reply = chat_answer.reply.strip() or "I have no answer to that yet."

    if conversation is None:
        conversation = repository.create_conversation(account.id, generate_title(llm_client, question))
    repository.append_exchange(conversation.id, question, reply, chat_answer.chart)
    return ChatResponse(
        conversation_id=conversation.id, title=conversation.title, reply=reply, chart=chat_answer.chart
    )
