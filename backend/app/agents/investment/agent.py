import datetime
import logging
import math
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.config import get_settings
from app.forecasting.client import Forecast, Scenario
from app.service_client import ServiceClient

logger = logging.getLogger(__name__)

ProposalKind = Literal["fixed_term_deposit", "fixed_term_investment", "credit_line"]

TERM_DEPOSIT_FAMILY = "term_deposit"
SURPLUS_GROUP = "surplus_placement"
LIQUIDITY_GROUP = "liquidity_cover"
CREDIT_LINE_ROUNDING_EUR = 1000


class InstrumentOffer(BaseModel):
    """An eligible fixed-term offer as returned by the instrument recommendation agent."""

    offer_id: str
    name: str
    term_days: int
    currency: Literal["EUR"]
    min_amount: float
    max_amount: float
    annual_rate_pct: float
    forecast_limit_days: int | None = Field(default=None, gt=0)


class NotificationDraft(BaseModel):
    """E-mail draft the instrument agent wrote with the LLM."""

    subject: str
    body: str


class RecommendedFamily(BaseModel):
    """A product family the agent recommends, with all its eligible terms and the one it prefers."""

    family_id: str
    family_name: str
    recommended_offer_id: str
    reason: str
    variants: list[InstrumentOffer]

    @model_validator(mode="after")
    def validate_recommended_offer(self) -> "RecommendedFamily":
        """Reject a recommendation that points outside the family.

        Returns:
            The validated family.
        """
        if self.recommended_offer_id not in {offer.offer_id for offer in self.variants}:
            raise ValueError("The recommended offer must belong to the family.")
        return self


class InstrumentRecommendation(BaseModel):
    """Response of the instrument recommendation agent."""

    families: list[RecommendedFamily] = Field(max_length=3)
    notification: NotificationDraft


class Proposal(BaseModel):
    """A proposal shown to the owner; nothing happens until they approve it, and execution is simulated."""

    id: str
    group: str
    kind: ProposalKind
    title: str
    amount: float
    term_days: int | None = None
    annual_rate_pct: float | None = None
    min_amount: float | None = None
    interest_eur: float | None = None
    lowest_balance: float | None = None
    buffer_eur: float | None = None
    safe_amount: float | None = None
    forecast_limit_days: int | None = None
    family_id: str | None = None
    family_name: str | None = None
    family_rank: int | None = None
    is_recommended_term: bool = False
    family_recommendation_reason: str | None = None
    analysis: str
    recommendation: str
    rationale: str
    on_approval: str
    requires_approval: bool = True
    execution_mode: Literal["simulated"] = "simulated"


class InstrumentAgentClient:
    """Calls the instrument recommendation agent (`instrument_recommendation_agent/`)."""

    def __init__(self, service_client: ServiceClient) -> None:
        """Wrap the HTTP client.

        Args:
            service_client: HTTP client pointed at the instrument agent.
        """
        self._service_client = service_client

    @property
    def configured(self) -> bool:
        """Whether the instrument agent URL is configured.

        Returns:
            `True` if recommendations can be requested.
        """
        return self._service_client.configured

    def recommend(self, forecast: Forecast) -> InstrumentRecommendation:
        """Ask the agent which product families fit the forecast's official safe-to-lock limits.

        Args:
            forecast: The current balance forecast.

        Returns:
            Up to three ranked families with their eligible terms, and an e-mail draft.
        """
        payload = self._service_client.request_json(
            "POST",
            "/recommendations",
            json={
                "account_id": forecast.account_id,
                "as_of": forecast.as_of.isoformat(),
                "official": {
                    "safe_to_lock": [
                        limit.model_dump(mode="json") for limit in forecast.official.safe_to_lock
                    ]
                },
            },
        )
        return InstrumentRecommendation.model_validate(payload)


def format_euro(amount: float) -> str:
    """Format an amount as euros for proposal texts.

    Args:
        amount: Amount in EUR.

    Returns:
        The formatted amount, e.g. `€7,391.53` or `−€1,200.00`.
    """
    sign = "−" if amount < 0 else ""
    return f"{sign}€{abs(amount):,.2f}"


def _format_date(day: datetime.date) -> str:
    """Format a date for proposal texts.

    Args:
        day: Calendar date.

    Returns:
        The date, e.g. `31 Dec 2025`.
    """
    return f"{day.day} {day:%b %Y}"


def _buffer_explanation(scenario: Scenario) -> str:
    """Describe where the cash buffer comes from.

    Args:
        scenario: Forecast scenario with the buffer.

    Returns:
        A short phrase about the buffer.
    """
    if scenario.buffer.source == "suggested":
        return f"a cash buffer of {format_euro(scenario.buffer.amount)} (one month of scheduled payments)"
    return f"your cash buffer of {format_euro(scenario.buffer.amount)}"


def deposit_proposal(
    forecast: Forecast,
    offer: InstrumentOffer,
    *,
    family: RecommendedFamily,
    family_rank: int,
) -> Proposal:
    """Explain one eligible fixed-term offer with the forecast numbers behind it.

    Args:
        forecast: The current balance forecast.
        offer: An eligible variant of the family.
        family: The recommended product family the variant belongs to.
        family_rank: Position of the family in the agent's ranking, starting at 1.

    Returns:
        The proposal for the owner.

    Raises:
        ValueError: If the forecast has no limit covering the offer's term, or the offer's amounts do not
            fit that limit (the agent must never propose more than the forecast allows).

    Steps:
        1. Look up the safe-to-lock limit that covers the offer's term.
        2. Check that the offered amounts stay within that limit.
        3. Compute the illustrative return for the offered amount and term.
        4. Write the analysis, recommendation, rationale and approval effect from those numbers.
    """
    scenario = forecast.official
    limit_days = offer.forecast_limit_days or offer.term_days
    limit = next((entry for entry in scenario.safe_to_lock if entry.days == limit_days), None)
    if limit is None or limit_days < offer.term_days:
        raise ValueError(f"Offer {offer.offer_id} has no forecast limit covering {offer.term_days} days.")
    if not 0 < offer.min_amount <= offer.max_amount <= limit.amount:
        raise ValueError(f"Offer {offer.offer_id} amounts do not fit the forecast limit.")

    interest = round(offer.max_amount * offer.annual_rate_pct / 100 * offer.term_days / 365, 2)
    capped = offer.max_amount < limit.amount
    cap_note = f", capped at the offer's maximum of {format_euro(offer.max_amount)}" if capped else ""
    is_deposit = family.family_id == TERM_DEPOSIT_FAMILY
    return Proposal(
        id=f"{forecast.account_id}-{offer.offer_id}-{forecast.as_of.isoformat()}",
        group=SURPLUS_GROUP,
        kind="fixed_term_deposit" if is_deposit else "fixed_term_investment",
        title=f"Put {format_euro(offer.max_amount)} into a {offer.name}",
        amount=offer.max_amount,
        term_days=offer.term_days,
        annual_rate_pct=offer.annual_rate_pct,
        min_amount=offer.min_amount,
        interest_eur=interest,
        lowest_balance=limit.lowest_balance,
        buffer_eur=scenario.buffer.amount,
        safe_amount=limit.amount,
        forecast_limit_days=limit_days,
        family_id=family.family_id,
        family_name=family.family_name,
        family_rank=family_rank,
        is_recommended_term=offer.offer_id == family.recommended_offer_id,
        family_recommendation_reason=family.reason,
        analysis=(
            f"Your balance on {_format_date(forecast.as_of)} was {format_euro(forecast.start_balance)}. "
            f"Even in a bad case, the balance should not drop below {format_euro(limit.lowest_balance)} "
            f"in the next {limit_days} days. After keeping {_buffer_explanation(scenario)}, "
            f"{format_euro(limit.amount)} is not needed in that period."
        ),
        recommendation=(
            f"You could place up to {format_euro(offer.max_amount)} in the {offer.name} "
            f"at an illustrative {offer.annual_rate_pct:g} % a year. "
            "All placement offers use the same cash, so choose at most one."
        ),
        rationale=(
            f"Safe amount = lowest balance in a bad case {format_euro(limit.lowest_balance)} − buffer "
            f"{format_euro(scenario.buffer.amount)} = {format_euro(limit.amount)}{cap_note}. "
            f"Illustrative gross return over {offer.term_days} days: about {format_euro(interest)}. "
            "Demo offer; rates are not real quotes."
        ),
        on_approval=(
            f"A simulated placement of {format_euro(offer.max_amount)} in the {offer.name} for "
            f"{offer.term_days} days is recorded and you get a confirmation. No real money moves."
        ),
    )


def credit_line_proposal(forecast: Forecast) -> Proposal | None:
    """Propose a credit line when the forecast shows the balance may go below zero.

    Args:
        forecast: The current balance forecast.

    Returns:
        The proposal, or `None` if the pessimistic balance stays positive.

    Steps:
        1. Find the lowest pessimistic (p5) balance in the forecast horizon.
        2. Stop if it stays above zero.
        3. Size the credit line to cover the gap, rounded up to the next €1,000.
    """
    scenario = forecast.official
    lowest_day = min(scenario.daily, key=lambda band: band.p5)
    if lowest_day.p5 >= 0:
        return None
    credit_amount = math.ceil(-lowest_day.p5 / CREDIT_LINE_ROUNDING_EUR) * CREDIT_LINE_ROUNDING_EUR
    return Proposal(
        id=f"{forecast.account_id}-credit_line-{forecast.as_of.isoformat()}",
        group=LIQUIDITY_GROUP,
        kind="credit_line",
        title=f"Arrange a credit line of {format_euro(credit_amount)}",
        amount=credit_amount,
        lowest_balance=lowest_day.p5,
        analysis=(
            f"In a bad case your balance could fall to {format_euro(lowest_day.p5)} around "
            f"{_format_date(lowest_day.date)}. The chance of going below zero in the next "
            f"{len(scenario.daily)} days is about {scenario.p_below_zero:.0%}."
        ),
        recommendation=(
            f"Arrange a credit line of {format_euro(credit_amount)} now, before the gap appears, "
            "so rent, payroll and suppliers can be paid on time."
        ),
        rationale=(
            f"Credit line = lowest balance in a bad case {format_euro(lowest_day.p5)}, "
            f"rounded up to the next {format_euro(CREDIT_LINE_ROUNDING_EUR)}. "
            "Terms would need a separate quote from the bank."
        ),
        on_approval=(
            f"A simulated credit line of {format_euro(credit_amount)} is recorded "
            "and you get a confirmation. No real contract is signed."
        ),
    )


@lru_cache
def get_instrument_agent_client() -> InstrumentAgentClient:
    """Create the instrument agent client once per process.

    Returns:
        The shared instrument agent client.
    """
    settings = get_settings()
    return InstrumentAgentClient(
        ServiceClient("instrument agent", settings.instrument_api_url, settings.instrument_timeout_seconds)
    )
