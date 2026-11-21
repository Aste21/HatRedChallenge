import json
import os
from collections.abc import Callable
from datetime import date
from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from tools import list_offers, make_evaluate_offer


class NotificationDraft(BaseModel):
    subject: str = Field(description="Short email subject on one line.")
    body: str = Field(description="Plain-text email body.")


SYSTEM_PROMPT = """
Write an English email draft about the supplied deposit evaluation.

Use only the evaluated offers and facts supplied in the request.
Describe eligible offers as alternatives that draw from the same cash.
Present amounts as forecast-based limits and invite the recipient to
review an offer in the app. Identify the offers as demo offers.
If no offer qualifies, explain why using the evaluation results.
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


def draft_notification(
    *,
    as_of: date,
    evaluations: list[dict],
    model: ChatOpenAI | None = None,
) -> NotificationDraft:
    agent = create_agent(
        model=model if model is not None else get_model(),
        response_format=ToolStrategy(NotificationDraft),
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
    draft: Callable[..., NotificationDraft] = draft_notification,
) -> tuple[list[dict], NotificationDraft]:
    evaluate_offer = make_evaluate_offer(safe_to_lock_eur=safe_to_lock_eur)
    catalog = list_offers.invoke({})
    offers = []
    evaluations = []

    for offer in catalog:
        evaluation = evaluate_offer.invoke({"offer_id": offer["offer_id"]})
        evaluations.append(evaluation)

        if evaluation["status"] == "eligible":
            offers.append(
                {
                    "offer_id": offer["offer_id"],
                    "name": offer["name"],
                    "term_days": offer["term_days"],
                    "currency": "EUR",
                    "min_amount": f"{offer['min_amount_eur']:.2f}",
                    "max_amount": f"{evaluation['max_amount_eur']:.2f}",
                    "annual_rate_pct": offer["annual_rate_pct"],
                }
            )

    notification = draft(as_of=as_of, evaluations=evaluations)
    return offers, notification