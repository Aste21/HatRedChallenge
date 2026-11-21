from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.accounts import AccountProfile, get_account
from app.storage.conversations import (
    Conversation,
    ConversationRepository,
    ConversationSummary,
    get_conversation_repository,
)

router = APIRouter(prefix="/api/conversations", tags=["chat"])


class ConversationList(BaseModel):
    """Chat history overview, most recently active first."""

    conversations: list[ConversationSummary]


@router.get("", response_model=ConversationList)
def list_conversations(
    account: Annotated[AccountProfile, Depends(get_account)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ConversationList:
    """List stored conversations for the history view.

    Args:
        account: The signed-in account.
        repository: Injected chat history store.
        limit: Maximum number of conversations to return.

    Returns:
        The conversation summaries.
    """
    return ConversationList(conversations=repository.list_conversations(account.id, limit))


@router.get("/{conversation_id}", response_model=Conversation)
def get_conversation(
    conversation_id: str,
    account: Annotated[AccountProfile, Depends(get_account)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> Conversation:
    """Load one conversation with all of its messages.

    Args:
        conversation_id: Id of the conversation.
        account: The signed-in account.
        repository: Injected chat history store.

    Returns:
        The conversation.
    """
    conversation = repository.get_conversation(account.id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="This conversation no longer exists.")
    return conversation


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    account: Annotated[AccountProfile, Depends(get_account)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> Response:
    """Delete a conversation and its messages.

    Args:
        conversation_id: Id of the conversation.
        account: The signed-in account.
        repository: Injected chat history store.

    Returns:
        An empty 204 response.
    """
    if not repository.delete_conversation(account.id, conversation_id):
        raise HTTPException(status_code=404, detail="This conversation no longer exists.")
    return Response(status_code=204)
