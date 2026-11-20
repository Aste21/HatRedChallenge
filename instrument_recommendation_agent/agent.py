from langchain.agents import create_agent
from tools import list_offers, make_evaluate_offer

evaluate_offer = make_evaluate_offer(
    as_of=as_of,  # Date of the current balance
    current_balance_pln=request.current_balance_pln,
    minimum_reserve_pln=request.minimum_reserve_pln,
    forecast={point.date: point.balance_pln for point in request.forecast},
)

agent = create_agent(
    model=model,
    tools=[list_offers, evaluate_offer],
    system_prompt=(
        "Recommend instruments for the supplied balance forecast. "
        "Look up offers and evaluate each offer you intend to recommend. "
        "Use the amounts and dates returned by the tools. "
        "If no offer fits, explain which constraints rule them out."
    ),
)
