import os
from datetime import date
from functools import lru_cache

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from tools import list_offers, make_evaluate_offer


SYSTEM_PROMPT = """
Recommend suitable instruments from the fictional EUR offer catalog.

1. Call list_offers to get the available offers.
2. Call evaluate_offer for every listed offer ID.
3. Recommend only offers marked eligible. Use the amount and term returned
   by the tool.
4. Present eligible offers as alternatives because they draw from the same
   cash. Give the maximum amount for each alternative.
5. Explain any missing forecast durations or amounts below an offer's minimum.
6. If no offer qualifies, say so and explain the tool results.

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
    safe_to_lock_eur: dict[int, float],
) -> str:
    evaluate_offer = make_evaluate_offer(safe_to_lock_eur=safe_to_lock_eur)

    agent = create_agent(
        model=get_model(),
        tools=[list_offers, evaluate_offer],
        system_prompt=SYSTEM_PROMPT,
    )

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Evaluate the catalog using the official forecast "
                        f"based on the statement as of {as_of.isoformat()}."
                    ),
                }
            ]
        }
    )
    return result["messages"][-1].text