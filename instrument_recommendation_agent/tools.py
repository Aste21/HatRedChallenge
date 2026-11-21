from datetime import date, timedelta

from langchain.tools import tool


# Fictional offers for the demo.
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
    """List demo term deposits and the offer IDs used by evaluate_offer."""
    return [
        {"offer_id": offer_id, **terms}
        for offer_id, terms in OFFERS.items()
    ]


def make_evaluate_offer(
    *,
    as_of: date,
    current_balance_pln: int,
    minimum_reserve_pln: int,
    forecast: dict[date, int],
):
    """Create an evaluation tool bound to the current request's forecast."""

    @tool
    def evaluate_offer(offer_id: str) -> dict:
        """Evaluate one catalog offer by ID against the forecast and cash reserve."""
        offer = OFFERS.get(offer_id)
        if offer is None:
            return {"offer_id": offer_id, "status": "unknown_offer"}

        release_date = as_of + timedelta(days=offer["term_days"])
        result = {
            "offer_id": offer_id,
            "release_date": release_date.isoformat(),
        }

        forecast_through = max(forecast, default=as_of)
        if forecast_through < release_date:
            return {
                **result,
                "status": "insufficient_forecast",
                "forecast_through": forecast_through.isoformat(),
            }

        balances_during_term = [
            balance
            for day, balance in forecast.items()
            if as_of <= day <= release_date
        ]
        lowest_balance = min([current_balance_pln, *balances_during_term])
        available_pln = max(0, lowest_balance - minimum_reserve_pln)
        max_amount_pln = min(available_pln, offer["max_amount_pln"])

        if max_amount_pln < offer["min_amount_pln"]:
            return {
                **result,
                "status": "below_minimum",
                "available_pln": available_pln,
                "required_minimum_pln": offer["min_amount_pln"],
                "reserve_shortfall_pln": max(
                    0, minimum_reserve_pln - lowest_balance
                ),
            }

        return {
            **result,
            "status": "eligible",
            "provisional_max_amount_pln": max_amount_pln,
            "lowest_forecast_balance_pln": lowest_balance,
            "annual_rate_pct": offer["annual_rate_pct"],
        }

    return evaluate_offer
    