import datetime
import json
import logging
import smtplib
import threading
import time
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel

from app.agents.investment.agent import (
    InstrumentAgentClient,
    NotificationDraft,
    Proposal,
    SURPLUS_GROUP,
    credit_line_proposal,
    deposit_proposal,
    format_euro,
    get_instrument_agent_client,
)
from app.config import Settings, get_settings
from app.forecasting.client import Forecast, ForecastClient, get_forecast_client
from app.notifications.email import send_email, smtp_configured
from app.service_client import ServiceUnavailableError
from app.storage.decisions import (
    Decision,
    DecisionRepository,
    SimulatedTransaction,
    StoredDecision,
    StoredNotification,
    get_decision_repository,
    new_id,
    now_iso,
)

logger = logging.getLogger(__name__)

RECOMMENDATION_CACHE_SECONDS = 15 * 60
IN_APP_RECIPIENT = "owner (in-app outbox)"

ProposalStatus = Literal["awaiting_approval", "approved", "declined", "superseded"]


class ProposalView(Proposal):
    """A proposal together with the owner's decision so far."""

    status: ProposalStatus
    decided_at: str | None = None


class ProposalBoard(BaseModel):
    """Everything the proposals page shows."""

    as_of: datetime.date
    start_balance: float
    proposals: list[ProposalView]
    notification_draft: NotificationDraft | None
    warnings: list[str]


class ProposalNotFoundError(LookupError):
    """The proposal does not exist (any more), e.g. because a newer statement changed the forecast."""


class DecisionConflictError(RuntimeError):
    """The proposal was already decided, or an alternative from the same group was already approved."""


class DecisionResult(BaseModel):
    """Outcome of a decision: the updated proposal, the simulated transaction and the notification status."""

    proposal: ProposalView
    transaction: SimulatedTransaction | None
    notification_status: str | None


class ProposalService:
    """Builds proposals from the forecast and the instrument agent and records the owner's decisions."""

    def __init__(
        self,
        settings: Settings,
        forecast_client: ForecastClient,
        instrument_agent_client: InstrumentAgentClient,
        repository: DecisionRepository,
    ) -> None:
        """Wire the service to its collaborators.

        Args:
            settings: Application settings (notification delivery).
            forecast_client: Client for the forecast service.
            instrument_agent_client: Client for the instrument recommendation agent.
            repository: Store for decisions, simulated transactions and notifications.
        """
        self._settings = settings
        self._forecast_client = forecast_client
        self._instrument_agent_client = instrument_agent_client
        self._repository = repository
        self._lock = threading.Lock()
        self._cached: dict[
            str, tuple[float, tuple[datetime.date, str], list[Proposal], NotificationDraft | None, list[str]]
        ] = {}

    def board(self, account_id: str) -> ProposalBoard:
        """Current proposals for an account with their decision status.

        Args:
            account_id: The signed-in account.

        Returns:
            The proposals page content.

        Steps:
            1. Forecast the balance (fast; raises `ServiceUnavailableError` if the forecast service is down).
            2. Reuse the instrument agent's answer for the same forecast
               for 15 minutes, because it calls the LLM and takes several seconds.
            3. Merge the stored decisions: an approval in a group supersedes its alternatives.
        """
        forecast = self._forecast_client.fetch_forecast(account_id)
        forecast_key = (
            forecast.as_of,
            json.dumps(
                forecast.model_dump(mode="json"), sort_keys=True
            ),
        )
        with self._lock:
            cached = self._cached.get(account_id)
            if (
                cached is None
                or cached[1] != forecast_key
                or time.monotonic() - cached[0] > RECOMMENDATION_CACHE_SECONDS
            ):
                proposals, draft, warnings = self._build_proposals(forecast)
                cached = (time.monotonic(), forecast_key, proposals, draft, warnings)
                if not warnings:
                    self._cached[account_id] = cached
        _, (as_of, _), proposals, draft, warnings = cached

        decisions = self._repository.list_decisions(account_id)
        # Keep surplus approvals for the same statement even if the shortlist changes.
        current_ids = {proposal.id for proposal in proposals}
        approved_groups = {
            decision.proposal_group
            for proposal_id, decision in decisions.items()
            if decision.decision == "approved"
            and (
                proposal_id in current_ids
                or (
                    decision.proposal_group == SURPLUS_GROUP
                    and proposal_id.endswith(f"-{as_of.isoformat()}")
                )
            )
        }
        views = []
        for proposal in proposals:
            decision = decisions.get(proposal.id)
            if decision is not None:
                status: ProposalStatus = decision.decision
            elif proposal.group in approved_groups:
                status = "superseded"
            else:
                status = "awaiting_approval"
            views.append(
                ProposalView(
                    **proposal.model_dump(),
                    status=status,
                    decided_at=decision.decided_at if decision else None,
                )
            )
        return ProposalBoard(
            as_of=as_of,
            start_balance=forecast.start_balance,
            proposals=views,
            notification_draft=draft,
            warnings=warnings,
        )

    def _build_proposals(
        self, forecast: Forecast
    ) -> tuple[list[Proposal], NotificationDraft | None, list[str]]:
        """Turn the forecast into proposals, asking the instrument agent for investment offers.

        Args:
            forecast: The current balance forecast.

        Returns:
            Proposals, the agent's e-mail draft (if any) and warnings for parts that could not be built.
        """
        proposals: list[Proposal] = []
        warnings: list[str] = []
        credit_line = credit_line_proposal(forecast)
        if credit_line is not None:
            proposals.append(credit_line)

        draft: NotificationDraft | None = None
        try:
            recommendation = self._instrument_agent_client.recommend(forecast)
            placements = [
                deposit_proposal(forecast, offer, family=family, family_rank=rank)
                for rank, family in enumerate(recommendation.families, start=1)
                for offer in family.variants
            ]
        except (ServiceUnavailableError, ValueError) as error:
            logger.warning("Investment proposals unavailable: %s", error)
            warnings.append("Investment offers are not available.")
        else:
            draft = recommendation.notification
            proposals.extend(placements)
        return proposals, draft, warnings

    def decide(self, account_id: str, proposal_id: str, decision: Decision) -> DecisionResult:
        """Record the owner's decision; an approval creates a simulated transaction and a notification.

        Args:
            account_id: The signed-in account.
            proposal_id: Id of the proposal.
            decision: `approved` or `declined`.

        Returns:
            The updated proposal, the simulated transaction and the notification status.

        Steps:
            1. Find the proposal on the current board; refuse unknown or already decided proposals and a
               second approval in the same group (alternatives use the same cash).
            2. For an approval, prepare the simulated transaction and the confirmation e-mail.
            3. Store everything in one transaction, then deliver the e-mail if SMTP is configured
               (otherwise it stays in the in-app outbox).
        """
        board = self.board(account_id)
        proposal = next((item for item in board.proposals if item.id == proposal_id), None)
        if proposal is None:
            raise ProposalNotFoundError(proposal_id)
        if proposal.status != "awaiting_approval":
            raise DecisionConflictError(f"This proposal is already {proposal.status.replace('_', ' ')}.")

        decided_at = now_iso()
        stored_decision = StoredDecision(
            proposal_id=proposal.id,
            proposal_group=proposal.group,
            decision=decision,
            title=proposal.title,
            amount=proposal.amount,
            decided_at=decided_at,
        )
        transaction: SimulatedTransaction | None = None
        notification: StoredNotification | None = None
        if decision == "approved":
            transaction = SimulatedTransaction(
                id=new_id(),
                proposal_id=proposal.id,
                kind=proposal.kind,
                description=proposal.title,
                amount=proposal.amount,
                created_at=decided_at,
            )
            notification = StoredNotification(
                id=new_id(),
                recipient=self._settings.owner_email or IN_APP_RECIPIENT,
                subject=f"Approved (simulated): {proposal.title}",
                body=(
                    f"You approved: {proposal.title}.\n\n"
                    f"Amount: {format_euro(proposal.amount)}\n"
                    f"Why: {proposal.rationale}\n\n"
                    f"{proposal.on_approval}\n"
                ),
                status="queued",
                created_at=decided_at,
            )
        self._repository.record_decision(account_id, stored_decision, transaction, notification)

        notification_status = self._deliver(notification) if notification is not None else None
        updated = proposal.model_copy(update={"status": decision, "decided_at": decided_at})
        return DecisionResult(
            proposal=updated, transaction=transaction, notification_status=notification_status
        )

    def _deliver(self, notification: StoredNotification) -> str:
        """Send a queued notification by e-mail when SMTP is configured.

        Args:
            notification: The stored notification.

        Returns:
            The resulting delivery status.
        """
        if not smtp_configured(self._settings):
            return "queued"
        try:
            send_email(self._settings, notification.recipient, notification.subject, notification.body)
        except (OSError, smtplib.SMTPException):
            logger.exception("Sending the notification e-mail failed")
            self._repository.set_notification_status(notification.id, "failed")
            return "failed"
        self._repository.set_notification_status(notification.id, "sent")
        return "sent"


@lru_cache
def get_proposal_service() -> ProposalService:
    """Create the proposal service once per process.

    Returns:
        The shared proposal service.
    """
    return ProposalService(
        get_settings(), get_forecast_client(), get_instrument_agent_client(), get_decision_repository()
    )
