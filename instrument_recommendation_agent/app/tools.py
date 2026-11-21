from decimal import ROUND_DOWN, Decimal

from langchain.tools import tool


# Fictional offers for the demo.
OFFERS = {
    "deposit_30d": {
        "name": "Demo 30-day deposit",
        "term_days": 30,
        "annual_rate_pct": 3.5,
        "min_amount_eur": 1_000,
        "max_amount_eur": 20_000,
    },
    "deposit_60d": {
        "name": "Demo 60-day deposit",
        "term_days": 60,
        "annual_rate_pct": 3.8,
        "min_amount_eur": 1_500,
        "max_amount_eur": 25_000,
    },
    "deposit_90d": {
        "name": "Demo 90-day deposit",
        "term_days": 90,
        "annual_rate_pct": 4.2,
        "min_amount_eur": 2_000,
        "max_amount_eur": 30_000,
    },
}


@tool
def list_offers() -> list[dict]:
    """List demo EUR deposits and the offer IDs used by evaluate_offer."""
    return [
        {"offer_id": offer_id, **offer}
        for offer_id, offer in OFFERS.items()
    ]


def make_evaluate_offer(*, safe_to_lock_eur: dict[int, float]):
    """Create an evaluation tool using the official limits for this request."""

    @tool
    def evaluate_offer(offer_id: str) -> dict:
        """Check one offer against the official limit for its exact term."""
        offer = OFFERS.get(offer_id)
        if offer is None:
            return {"offer_id": offer_id, "status": "unknown_offer"}

        term_days = offer["term_days"]
        result = {
            "offer_id": offer_id,
            "name": offer["name"],
            "term_days": term_days,
        }

        forecast_limit = safe_to_lock_eur.get(term_days)
        if forecast_limit is None:
            return {**result, "status": "missing_forecast_duration"}

        available = Decimal(str(forecast_limit))
        offer_maximum = Decimal(offer["max_amount_eur"])
        max_amount = min(available, offer_maximum).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )

        if max_amount < offer["min_amount_eur"]:
            return {
                **result,
                "status": "below_minimum",
                "forecast_limit_eur": forecast_limit,
                "min_amount_eur": offer["min_amount_eur"],
            }

        return {
            **result,
            "status": "eligible",
            "max_amount_eur": float(max_amount),
            "annual_rate_pct": offer["annual_rate_pct"],
        }

    return evaluate_offer