from datetime import date, timedelta
from langchain.tools import tool

OFFERS = {
    "deposit_30d": {
        "name": "Demo 30-day deposit",
        "term_days": 30,
        "annual_rate_pct": 3.5,
        "min_amount_pln": 1_000,
        "max_amount_pln": 20_000,
    },
    "deposit_90d": {
        "name": "Demo 90-day deposit",
        "term_days": 90,
        "annual_rate_pct": 4.2,
        "min_amount_pln": 2_000,
        "max_amount_pln": 30_000,
    },
}


@tool
def list_offers() -> list[dict]:
    """List demo term deposits and their terms. Use the IDs to evaluate offers."""
    return [{"offer_id": offer_id, **terms} for offer_id, terms in OFFERS.items()]


def make_evaluate_offer(
    *,
    as_of: date,
    current_balance_pln: int,
    minimum_reserve_pln: int,
    forecast: dict[date, int],
):
    @tool
    def evaluate_offer(offer_id: str) -> dict:
        """Check whether a catalog offer fits the balance forecast and cash reserve."""
        offer = OFFERS.get(offer_id)
        if offer is None:
            return {"offer_id": offer_id, "status": "unknown_offer"}

        release_date = as_of + timedelta(days=offer["term_days"])
        result = {
            "offer_id": offer_id,
            "release_date": release_date.isoformat(),
        }

        if not forecast or max(forecast) < release_date:
            return {**result, "status": "insufficient_forecast"}

        balances_during_term = [
            balance for day, balance in forecast.items() if as_of <= day <= release_date
        ]
        lowest_balance = min([current_balance_pln, *balances_during_term])
        available = max(0, lowest_balance - minimum_reserve_pln)
        max_amount = min(available, offer["max_amount_pln"])

        if max_amount < offer["min_amount_pln"]:
            return {
                **result,
                "status": "below_minimum",
                "available_pln": available,
                "required_minimum_pln": offer["min_amount_pln"],
            }

        return {
            **result,
            "status": "eligible",
            "provisional_max_amount_pln": max_amount,
            "lowest_forecast_balance_pln": lowest_balance,
            "annual_rate_pct": offer["annual_rate_pct"],
        }

    return evaluate_offer
