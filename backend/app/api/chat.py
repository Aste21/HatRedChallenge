import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from pydantic import BaseModel, Field

from app.agents.chat.agent import ChatMessage, PageContext, answer, generate_title
from app.llm import LlmClient, get_llm_client
from app.storage.conversations import (
    ConversationRepository,
    ConversationSummary,
    get_conversation_repository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """A new user message; the history is loaded from storage by `conversation_id`."""

    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    page_context: PageContext | None = None


class ChatResponse(BaseModel):
    """The assistant's reply plus the conversation it was stored in."""

    conversation_id: str
    title: str
    reply: str


@router.post("", response_model=ChatResponse)
def post_chat(
    request: ChatRequest,
    llm_client: Annotated[LlmClient, Depends(get_llm_client)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> ChatResponse:
    """Answer a user message and store the exchange in the chat history.

    Args:
        request: The new message, the optional conversation it belongs to and the visible page content.
        llm_client: Injected LLM client.
        repository: Injected chat history store.

    Returns:
        The assistant reply with the conversation id and title.

    Steps:
        1. Load the existing conversation (404 if the id is unknown) or start with an empty history.
        2. Ask the chat agent for a reply; map LLM failures to HTTP 502 without storing anything,
           so the UI can simply retry.
        3. For a new conversation, generate its title from the first message and create it.
        4. Store the question and the reply together.
    """
    question = request.message.strip()
    if not question:
        raise HTTPException(status_code=422, detail="The message must not be empty.")
    conversation: ConversationSummary | None = None
    history: list[ChatMessage] = []
    if request.conversation_id is not None:
        conversation = repository.get_conversation(request.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="This conversation no longer exists.")
        history = [
            ChatMessage(role=message.role, content=message.content) for message in conversation.messages
        ]
    history.append(ChatMessage(role="user", content=question))

    try:
        reply = answer(llm_client, history, request.page_context)
    except OpenAIError as error:
        logger.exception("LLM call failed")
        raise HTTPException(
            status_code=502, detail="The language model is not reachable right now."
        ) from error
    reply = reply.strip() or "I have no answer to that yet."

    if conversation is None:
        conversation = repository.create_conversation(generate_title(llm_client, question))
    repository.append_exchange(conversation.id, question, reply)
    return ChatResponse(conversation_id=conversation.id, title=conversation.title, reply=reply)
