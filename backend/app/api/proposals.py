from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.accounts import AccountProfile, get_account
from app.agents.investment.service import (
    IN_APP_RECIPIENT,
    DecisionConflictError,
    DecisionResult,
    ProposalBoard,
    ProposalNotFoundError,
    ProposalService,
    get_proposal_service,
)
from app.service_client import ServiceUnavailableError
from app.storage.decisions import (
    DecisionRepository,
    SimulatedTransaction,
    StoredNotification,
    get_decision_repository,
)

router = APIRouter(prefix="/api", tags=["proposals"])


class DecisionRequest(BaseModel):
    """The owner's answer to a proposal."""

    decision: Literal["approved", "declined"]


class TransactionList(BaseModel):
    """Simulated transactions recorded after approvals."""

    transactions: list[SimulatedTransaction]


class NotificationList(BaseModel):
    """Notification outbox."""

    notifications: list[StoredNotification]


@router.get("/proposals", response_model=ProposalBoard)
def list_proposals(
    account: Annotated[AccountProfile, Depends(get_account)],
    service: Annotated[ProposalService, Depends(get_proposal_service)],
) -> ProposalBoard:
    """Current proposals (credit line, fixed-term deposits) with their decision status.

    Args:
        account: The signed-in account.
        service: Injected proposal service.

    Returns:
        The proposals page content.
    """
    try:
        return service.board(account.id)
    except ServiceUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/proposals/{proposal_id}/decision", response_model=DecisionResult)
def decide_proposal(
    proposal_id: str,
    request: DecisionRequest,
    account: Annotated[AccountProfile, Depends(get_account)],
    service: Annotated[ProposalService, Depends(get_proposal_service)],
) -> DecisionResult:
    """Approve or decline a proposal. Approval records a simulated transaction and a notification.

    Args:
        proposal_id: Id of the proposal.
        request: The decision.
        account: The signed-in account.
        service: Injected proposal service.

    Returns:
        The updated proposal, the simulated transaction and the notification status.
    """
    try:
        return service.decide(account.id, proposal_id, request.decision)
    except ProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail="This proposal is no longer available.") from error
    except DecisionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ServiceUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/transactions", response_model=TransactionList)
def list_transactions(
    account: Annotated[AccountProfile, Depends(get_account)],
    repository: Annotated[DecisionRepository, Depends(get_decision_repository)],
) -> TransactionList:
    """Simulated transactions, newest first.

    Args:
        account: The signed-in account.
        repository: Injected decision store.

    Returns:
        The simulated transactions.
    """
    return TransactionList(transactions=repository.list_transactions(account.id))


@router.get("/notifications", response_model=NotificationList)
def list_notifications(
    account: Annotated[AccountProfile, Depends(get_account)],
    repository: Annotated[DecisionRepository, Depends(get_decision_repository)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> NotificationList:
    """Notification outbox, newest first.

    Args:
        account: The signed-in account.
        repository: Injected decision store.
        limit: Maximum number of notifications.

    Returns:
        The notifications.
    """
    notifications = repository.list_notifications(account.id, limit)
    entries = [
        item if item.recipient == IN_APP_RECIPIENT else item.model_copy(update={"recipient": "Business owner"})
        for item in notifications
    ]
    return NotificationList(notifications=entries)
