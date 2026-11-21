import json
import os
from datetime import date
from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from tools import list_offers, make_evaluate_offer


class NotificationDraft(BaseModel):
    subject: str = Field(description="Short, single-line email subject.")
    body: str = Field(description="Plain-text email body in English.")


class AgentDecision(BaseModel):
    ranked_offer_ids: list[str] = Field(
        max_length=3,
        description="Primary offer ID first, followed by up to two alternatives.",
    )
    notification: NotificationDraft


SYSTEM_PROMPT = """
Recommend one primary offer and up to two alternatives from the supplied
evaluations. Use only the facts and figures in the request.

Choose only offers marked eligible under the official forecast. Put the
primary offer first. Compare the lockup period, maximum amount available
for each offer, and any supplied return estimates and risk information.
Prefer a shorter lockup when estimated returns are close. If you choose
a longer lockup, explain what makes it worthwhile. Treat annualized rates
as annualized figures and use term return estimates only when supplied.

Include an alternative only if it offers a distinct benefit. Each option
draws from the same cash, so present the options as separate choices.

If no offer qualifies, return an empty ranked_offer_ids list and explain
why using the evaluation results.

Write the email in English. Lead with the primary recommendation and why
you chose it. Describe the maximum amount as a forecast-based limit and
invite the recipient to review the offer in the app.
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


def choose_offers(
    *,
    as_of: date,
    evaluations: list[dict],
) -> AgentDecision:
    agent = create_agent(
        model=get_model(),
        response_format=ToolStrategy(AgentDecision),
        system_prompt=SYSTEM_PROMPT,
    )

    payload = {
        "as_of": as_of.isoformat(),
        "currency": "EUR",
        "evaluations": evaluations,
    }
    result = agent.invoke(
        {"messages": [{"role": "user", "content": json.dumps(payload)}]}
    )
    return result["structured_response"]


def run_agent(
    *,
    as_of: date,
    safe_to_lock_eur: dict[int, float],
) -> tuple[list[dict], NotificationDraft]:
    evaluate_offer = make_evaluate_offer(safe_to_lock_eur=safe_to_lock_eur)
    catalog = list_offers.invoke({})
    evaluations = []
    offers_by_id = {}

    for offer in catalog:
        offer_id = offer["offer_id"]
        evaluation = evaluate_offer.invoke({"offer_id": offer_id})
        evaluations.append({**offer, **evaluation})

        if evaluation["status"] == "eligible":
            offers_by_id[offer_id] = {
                "offer_id": offer_id,
                "name": offer["name"],
                "term_days": offer["term_days"],
                "currency": "EUR",
                "min_amount": f"{offer['min_amount_eur']:.2f}",
                "max_amount": f"{evaluation['max_amount_eur']:.2f}",
                "annual_rate_pct": offer["annual_rate_pct"],
            }

    decision = choose_offers(as_of=as_of, evaluations=evaluations)
    ranked_ids = decision.ranked_offer_ids

    if (
        bool(ranked_ids) != bool(offers_by_id)
        or len(ranked_ids) != len(set(ranked_ids))
        or any(offer_id not in offers_by_id for offer_id in ranked_ids)
    ):
        raise ValueError("The model returned an invalid offer selection.")

    ranked_offers = [offers_by_id[offer_id] for offer_id in ranked_ids]
    return ranked_offers, decision.notification