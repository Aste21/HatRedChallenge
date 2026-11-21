from decimal import ROUND_DOWN, Decimal

from langchain.tools import tool


OFFERS = {
    "deposit_30d": {
        "name": "30-day deposit",
        "term_days": 30,
        "annual_rate_pct": 3.5,
        "min_amount_eur": 1_000,
        "max_amount_eur": 20_000,
    },
    "deposit_60d": {
        "name": "60-day deposit",
        "term_days": 60,
        "annual_rate_pct": 3.8,
        "min_amount_eur": 1_500,
        "max_amount_eur": 25_000,
    },
    "deposit_90d": {
        "name": "90-day deposit",
        "term_days": 90,
        "annual_rate_pct": 4.2,
        "min_amount_eur": 2_000,
        "max_amount_eur": 30_000,
    },
            "government_bill_30d": {
        "name": "30-Day Government Bill",
        "term_days": 30,
        "annual_rate_pct": 2.6,
        "min_amount_eur": 1_000,
        "max_amount_eur": 50_000,
    },
    "government_bill_90d": {
        "name": "90-Day Government Bill",
        "term_days": 90,
        "annual_rate_pct": 3.1,
        "min_amount_eur": 1_000,
        "max_amount_eur": 75_000,
    },
    "corporate_commercial_paper_60d": {
        "name": "60-Day Corporate Commercial Paper",
        "term_days": 60,
        "annual_rate_pct": 3.6,
        "min_amount_eur": 5_000,
        "max_amount_eur": 100_000,
    },
    "government_bond_1y": {
        "name": "1-Year Government Bond",
        "term_days": 365,
        "annual_rate_pct": 3.2,
        "min_amount_eur": 1_000,
        "max_amount_eur": 75_000,
    },
    "corporate_bond_2y": {
        "name": "2-Year Investment-Grade Corporate Bond",
        "term_days": 730,
        "annual_rate_pct": 4.0,
        "min_amount_eur": 2_000,
        "max_amount_eur": 50_000,
    },
    "eur_money_market_fund": {
        "name": "EUR Money Market Fund",
        "term_days": 14,
        "annual_rate_pct": 2.7,
        "min_amount_eur": 500,
        "max_amount_eur": 50_000,
    },
    "ultrashort_bond_etf": {
        "name": "EUR Ultrashort Bond ETF",
        "term_days": 180,
        "annual_rate_pct": 0.0,
        "min_amount_eur": 250,
        "max_amount_eur": 40_000,
    },
    "global_equity_etf": {
        "name": "Global Equity ETF",
        "term_days": 1_825,
        "annual_rate_pct": 0.0,
        "min_amount_eur": 250,
        "max_amount_eur": 25_000,
    },
    "european_dividend_etf": {
        "name": "European Dividend Equity ETF",
        "term_days": 1_825,
        "annual_rate_pct": 0.0,
        "min_amount_eur": 250,
        "max_amount_eur": 20_000,
    },
    "listed_infrastructure_stock": {
        "name": "Listed Infrastructure Company Shares",
        "term_days": 1_825,
        "annual_rate_pct": 0.0,
        "min_amount_eur": 100,
        "max_amount_eur": 10_000,
    },
}


@tool
def list_offers() -> list[dict]:
    """List EUR deposits and the offer IDs used by evaluate_offer."""
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