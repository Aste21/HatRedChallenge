from decimal import ROUND_DOWN, Decimal

from langchain.tools import tool


# Synthetic catalog. Each variant contains:
# offer_id, term_days, annual_rate_pct, min_amount_eur, max_amount_eur.
_FAMILY_CATALOG = {
    "term_deposit": (
        "Term Deposit",
        (
            ("deposit_14d", 14, 2.8, 500, 15_000),
            ("deposit_30d", 30, 3.5, 1_000, 20_000),
            ("deposit_45d", 45, 3.7, 1_000, 22_500),
            ("deposit_60d", 60, 3.8, 1_500, 25_000),
            ("deposit_90d", 90, 4.2, 2_000, 30_000),
            ("deposit_120d", 120, 4.3, 2_000, 35_000),
            ("deposit_180d", 180, 4.35, 2_000, 40_000),
            ("deposit_365d", 365, 4.4, 2_000, 45_000),
        ),
    ),
    "government_bill": (
        "Government Bill",
        (
            ("government_bill_30d", 30, 2.6, 1_000, 50_000),
            ("government_bill_60d", 60, 3.2, 1_000, 60_000),
            ("government_bill_90d", 90, 3.1, 1_000, 75_000),
            ("government_bill_180d", 180, 3.4, 1_000, 90_000),
        ),
    ),
    "corporate_commercial_paper": (
        "Corporate Commercial Paper",
        (
            ("corporate_commercial_paper_30d", 30, 3.7, 5_000, 75_000),
            ("corporate_commercial_paper_60d", 60, 3.6, 5_000, 100_000),
            ("corporate_commercial_paper_75d", 75, 4.0, 5_000, 100_000),
            ("corporate_commercial_paper_90d", 90, 4.4, 5_000, 100_000),
        ),
    ),
    "bank_certificate": (
        "Bank Certificate",
        (
            ("bank_certificate_30d", 30, 3.1, 500, 35_000),
            ("bank_certificate_45d", 45, 3.3, 500, 38_000),
            ("bank_certificate_60d", 60, 3.4, 500, 40_000),
            ("bank_certificate_90d", 90, 3.6, 500, 45_000),
        ),
    ),
    "municipal_note": (
        "Municipal Note",
        (
            ("municipal_note_30d", 30, 3.3, 2_000, 40_000),
            ("municipal_note_60d", 60, 3.5, 2_000, 50_000),
            ("municipal_note_90d", 90, 3.9, 2_000, 55_000),
            ("municipal_note_120d", 120, 4.0, 2_000, 60_000),
        ),
    ),
    "agency_note": (
        "Public Agency Note",
        (
            ("agency_note_30d", 30, 3.4, 1_000, 15_000),
            ("agency_note_60d", 60, 3.9, 1_500, 20_000),
            ("agency_note_75d", 75, 3.95, 1_500, 22_500),
            ("agency_note_90d", 90, 4.0, 2_000, 25_000),
        ),
    ),
    "supranational_note": (
        "Supranational Note",
        (
            ("supranational_note_30d", 30, 3.0, 1_000, 80_000),
            ("supranational_note_60d", 60, 3.3, 1_000, 90_000),
            ("supranational_note_90d", 90, 3.6, 1_000, 120_000),
            ("supranational_note_180d", 180, 3.8, 1_000, 150_000),
        ),
    ),
    "covered_bank_note": (
        "Covered Bank Note",
        (
            ("covered_bank_note_30d", 30, 3.6, 2_500, 30_000),
            ("covered_bank_note_45d", 45, 3.85, 2_500, 32_500),
            ("covered_bank_note_60d", 60, 4.0, 2_500, 35_000),
            ("covered_bank_note_90d", 90, 4.1, 2_500, 40_000),
        ),
    ),
    "bank_commercial_paper": (
        "Bank Commercial Paper",
        (
            ("bank_commercial_paper_30d", 30, 3.8, 10_000, 50_000),
            ("bank_commercial_paper_60d", 60, 4.1, 10_000, 60_000),
            ("bank_commercial_paper_90d", 90, 4.3, 10_000, 70_000),
            ("bank_commercial_paper_120d", 120, 4.45, 10_000, 80_000),
        ),
    ),
    "asset_backed_commercial_paper": (
        "Asset-Backed Commercial Paper",
        (
            ("asset_backed_commercial_paper_30d", 30, 3.9, 20_000, 40_000),
            ("asset_backed_commercial_paper_60d", 60, 4.2, 20_000, 50_000),
            ("asset_backed_commercial_paper_75d", 75, 4.35, 20_000, 55_000),
            ("asset_backed_commercial_paper_90d", 90, 4.5, 20_000, 60_000),
        ),
    ),
    "government_bond": (
        "Government Bond",
        (
            ("government_bond_1y", 365, 3.2, 1_000, 75_000),
            ("government_bond_2y", 730, 3.4, 1_000, 100_000),
        ),
    ),
    "corporate_bond": (
        "Investment-Grade Corporate Bond",
        (
            ("corporate_bond_1y", 365, 3.75, 2_000, 40_000),
            ("corporate_bond_2y", 730, 4.0, 2_000, 50_000),
        ),
    ),
}


# Retained catalog entries with holding periods rather than fixed maturities.
_MARKET_OFFERS = {
    "eur_money_market_fund": {
        "name": "EUR Money Market Fund",
        "holding_period_days": 14,
        "annual_rate_pct": 2.7,
        "min_amount_eur": 500,
        "max_amount_eur": 50_000,
    },
    "ultrashort_bond_etf": {
        "name": "EUR Ultrashort Bond ETF",
        "holding_period_days": 180,
        "annual_rate_pct": 0.0,
        "min_amount_eur": 250,
        "max_amount_eur": 40_000,
    },
    "global_equity_etf": {
        "name": "Global Equity ETF",
        "holding_period_days": 1_825,
        "annual_rate_pct": 0.0,
        "min_amount_eur": 250,
        "max_amount_eur": 25_000,
    },
    "european_dividend_etf": {
        "name": "European Dividend Equity ETF",
        "holding_period_days": 1_825,
        "annual_rate_pct": 0.0,
        "min_amount_eur": 250,
        "max_amount_eur": 20_000,
    },
    "listed_infrastructure_stock": {
        "name": "Listed Infrastructure Company Shares",
        "holding_period_days": 1_825,
        "annual_rate_pct": 0.0,
        "min_amount_eur": 100,
        "max_amount_eur": 10_000,
    },
}


OFFER_FAMILIES = {
    family_id: {
        "name": family_name,
        "offer_ids": tuple(variant[0] for variant in variants),
    }
    for family_id, (family_name, variants) in _FAMILY_CATALOG.items()
}

OFFERS = {
    **{
        offer_id: {
            "name": f"{term_days}-day {family_name}",
            "family_id": family_id,
            "family_name": family_name,
            "term_days": term_days,
            "annual_rate_pct": annual_rate_pct,
            "min_amount_eur": min_amount_eur,
            "max_amount_eur": max_amount_eur,
        }
        for family_id, (family_name, variants) in _FAMILY_CATALOG.items()
        for (
            offer_id,
            term_days,
            annual_rate_pct,
            min_amount_eur,
            max_amount_eur,
        ) in variants
    },
    **_MARKET_OFFERS,
}


@tool
def list_offers() -> list[dict]:
    """List fixed-term EUR offers and their catalog IDs."""
    return [
        {"offer_id": offer_id, **offer}
        for offer_id, offer in OFFERS.items()
        if "term_days" in offer
    ]


def make_evaluate_offer(*, safe_to_lock_eur: dict[int, Decimal]):
    """Bind the evaluation tool to the current request's forecast limits."""

    @tool
    def evaluate_offer(offer_id: str) -> dict:
        """Evaluate one fixed-term offer against the limit for its exact term."""
        offer = OFFERS.get(offer_id)
        if offer is None:
            return {"offer_id": offer_id, "status": "unknown_offer"}

        result = {"offer_id": offer_id, "name": offer["name"]}
        term_days = offer.get("term_days")
        if term_days is None:
            return {**result, "status": "unsupported_instrument"}

        result["term_days"] = term_days
        forecast_limit = safe_to_lock_eur.get(term_days)
        if forecast_limit is None:
            return {**result, "status": "missing_forecast_duration"}

        max_amount = min(
            Decimal(str(forecast_limit)),
            Decimal(offer["max_amount_eur"]),
        ).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

        if max_amount < offer["min_amount_eur"]:
            return {
                **result,
                "status": "below_minimum",
                "forecast_limit_eur": str(forecast_limit),
                "min_amount_eur": offer["min_amount_eur"],
            }

        return {
            **result,
            "status": "eligible",
            "max_amount_eur": str(max_amount),
            "annual_rate_pct": offer["annual_rate_pct"],
        }

    return evaluate_offer