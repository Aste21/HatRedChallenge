import json
import os
from datetime import date
from functools import lru_cache

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from tools import list_offers, make_evaluate_offer


SYSTEM_PROMPT = """
Recommend financial instruments using the offer catalog and evaluation tools.

1. Call list_offers to discover the available offers.
2. Call evaluate_offer for each offer before making a recommendation.
3. Recommend only offers that evaluate_offer marks as eligible.
4. Use the amounts and release dates returned by evaluate_offer.
5. Present eligible offers as alternatives. Their limits are provisional
   and cannot be added together.
6. If no offer is eligible, explain the reasons returned by the tools.

Write the final recommendation in English.
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


def run_agent(
    *,
    as_of: date,
    current_balance_pln: int,
    minimum_reserve_pln: int,
    forecast: dict[date, int],
) -> str:
    evaluate_offer = make_evaluate_offer(
        as_of=as_of,
        current_balance_pln=current_balance_pln,
        minimum_reserve_pln=minimum_reserve_pln,
        forecast=forecast,
    )

    agent = create_agent(
        model=get_model(),
        tools=[list_offers, evaluate_offer],
        system_prompt=SYSTEM_PROMPT,
    )

    task = {
        "task": "Evaluate the catalog and recommend suitable offers.",
        "as_of": as_of.isoformat(),
    }
    result = agent.invoke(
        {"messages": [{"role": "user", "content": json.dumps(task)}]}
    )
    return result["messages"][-1].text
