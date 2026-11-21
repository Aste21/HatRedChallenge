import json
import logging
import os
from collections import defaultdict


from collections.abc import Callable

from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from tools import list_offers, make_evaluate_offer


logger = logging.getLogger(__name__)


class NotificationDraft(BaseModel):
    subject: str = Field(min_length=1, max_length=160, pattern=r"^[^\r\n]+$")
    body: str = Field(min_length=1)


class OfferVariant(BaseModel):
    offer_id: str
    name: str
    term_days: int
    currency: Literal["EUR"]
    min_amount: str
    max_amount: str
    annual_rate_pct: float


class RecommendedFamily(BaseModel):
    family_id: str
    family_name: str
    recommended_offer_id: str
    reason: str
    variants: list[OfferVariant]


class FamilyChoice(BaseModel):
    offer_id: str = Field(description="Exact eligible offer ID for this family.")
    reason: str = Field(
        min_length=1,
        description="Why this family and its recommended duration fit the forecast.",
    )


class AgentDecision(BaseModel):
    choices: list[FamilyChoice] = Field(
        min_length=1,
        max_length=3,
        description="Ranked recommendations, with one offer ID per distinct family.",
    )
    notification: NotificationDraft


class InvalidRecommendationError(Exception):
    """The model did not return a valid selection from the eligible offers."""


SYSTEM_PROMPT = """
Recommend one to three distinct product families from eligible_families.
Use an exact offer_id from the supplied variants for each choice. Choose
only one variant per family_id, even when multiple durations are eligible.
The app includes the other eligible durations automatically.

Put the strongest recommendation first. Include another family only when
it offers a meaningful trade-off, such as a shorter lockup or a different
amount limit. Within each selected family, explain why the chosen duration
fits the forecast. Consider the lockup period, maximum eligible amount,
and stated annualized rate. Prefer a shorter term when the benefit of
waiting longer is unclear. Use only the figures and product facts supplied.

Write a short English email with a single-line subject. Cover the selected
families and preferred durations in the same order as choices. Describe
the amounts as forecast-based limits and invite the recipient to compare
eligible durations in the app. Each option draws from the same cash and
should be considered individually.
""".strip()


@lru_cache(maxsize=1)
def get_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ["MODEL_ID"],
        base_url=os.environ["MODEL_BASE_URL"],
        api_key=os.environ.get("MODEL_TOKEN") or "unused",
        temperature=0,
        timeout=30,
    )


def request_decision(messages: list[dict], model: ChatOpenAI | None = None) -> AgentDecision | None:
    """Request a structured family selection and draft from the configured model."""
    agent = create_agent(
        model=model if model is not None else get_model(),
        response_format=ToolStrategy(AgentDecision),
        system_prompt=SYSTEM_PROMPT,
    )
    return agent.invoke({"messages": messages}).get("structured_response")


def run_agent(
    *,
    as_of: date,
    safe_to_lock_eur: dict[int, Decimal],
    decide: Callable[[list[dict]], AgentDecision | None] = request_decision,
) -> tuple[list[RecommendedFamily], NotificationDraft]:

    evaluate_offer = make_evaluate_offer(safe_to_lock_eur=safe_to_lock_eur)
    variants_by_family: dict[str, list[OfferVariant]] = defaultdict(list)
    family_names: dict[str, str] = {}
    family_by_offer_id: dict[str, str] = {}

    for offer in list_offers.invoke({}):
        offer_id = offer["offer_id"]
        evaluation = evaluate_offer.invoke({"offer_id": offer_id})
        if evaluation["status"] != "eligible":
            continue

        family_id = offer["family_id"]
        family_names[family_id] = offer["family_name"]
        family_by_offer_id[offer_id] = family_id

        variants_by_family[family_id].append(
            OfferVariant(
                offer_id=offer_id,
                name=offer["name"],
                term_days=offer["term_days"],
                currency="EUR",
                min_amount=f"{offer['min_amount_eur']:.2f}",
                max_amount=evaluation["max_amount_eur"],
                annual_rate_pct=offer["annual_rate_pct"],
            )
        )

    if not variants_by_family:
        return [], NotificationDraft(
            subject="No eligible investment offers",
            body=(
                "No catalog offer qualified under the latest cash forecast. "
                "An offer needs a forecast limit for its term and enough "
                "available cash to meet its minimum."
            ),
        )

    for variants in variants_by_family.values():
        variants.sort(key=lambda variant: variant.term_days)

    payload = {
        "as_of": as_of.isoformat(),
        "eligible_families": [
            {
                "family_id": family_id,
                "family_name": family_names[family_id],
                "variants": [
                    variant.model_dump(mode="json") for variant in variants
                ],
            }
            for family_id, variants in variants_by_family.items()
        ],
    }
    request_message = {"role": "user", "content": json.dumps(payload)}



    messages = [request_message]

    for _ in range(2):
        decision = decide(messages)

        if not isinstance(decision, AgentDecision):
            error = "No structured AgentDecision was returned."
        else:
            families: list[RecommendedFamily] = []
            selected_family_ids: set[str] = set()

            for choice in decision.choices:
                family_id = family_by_offer_id.get(choice.offer_id)

                if family_id is None:
                    error = "A selected offer ID was absent from the eligible variants."
                    break

                if family_id in selected_family_ids:
                    error = f"Family {family_id!r} was selected more than once."
                    break

                selected_family_ids.add(family_id)
                families.append(
                    RecommendedFamily(
                        family_id=family_id,
                        family_name=family_names[family_id],
                        recommended_offer_id=choice.offer_id,
                        reason=choice.reason,
                        variants=variants_by_family[family_id],
                    )
                )
            else:
                return families, decision.notification

        messages = [
            request_message,
            {
                "role": "user",
                "content": (
                    f"The previous response failed validation: {error} "
                    "Return a corrected structured decision using one exact "
                    "eligible offer ID per selected family."
                ),
            },
        ]

    logger.warning("Invalid recommendation after retry: %s", error)
    raise InvalidRecommendationError(error)
