## Run locally with Docker
docker build -t instrument-agent .
docker run --rm -p 8080:8080 --env-file .env instrument-agent

## Test with curl
```bash
curl --fail-with-body -sS http://localhost:8080/recommendations \
  -H 'Content-Type: application/json' \
  -d '{
    "account_id": "account",
    "as_of": "2026-11-21",
    "official": {
      "safe_to_lock": [
        {"days": 30, "amount": 3000, "lowest_balance": 18000},
        {"days": 60, "amount": 1200, "lowest_balance": 16200},
        {"days": 90, "amount": 0, "lowest_balance": 15000}
      ]
    }
  }' | python3 -m json.tool
```

Wcześniej serwis zwracał coś w tym stylu:

```json
{
    "account_id": "account",
    "as_of": "2026-11-21",
    "offers": [
        {
            "offer_id": "deposit_30d",
            "name": "30-day deposit",
            "term_days": 30,
            "currency": "EUR",
            "min_amount": "1000.00",
            "max_amount": "3000.00",
            "annual_rate_pct": 3.5
        },
        {
            "offer_id": "government_bill_30d",
            "name": "30-Day Government Bill",
            "term_days": 30,
            "currency": "EUR",
            "min_amount": "1000.00",
            "max_amount": "3000.00",
            "annual_rate_pct": 2.6
        }
    ],
    "notification": {
        "subject": "Recommended deposit: 30-day deposit at 3.5%",
        "body": "Primary recommendation: 30-day deposit (deposit_30d).\n\nWhy this offer: It is one of only two offers marked eligible under the official forecast. It pays 3.5% annualized over a 30-day lockup, which is the highest eligible rate available. The forecast-based maximum amount you can allocate is EUR 3,000 (minimum EUR 1,000). The short 30-day lockup keeps your funds accessible sooner than any longer eligible alternative.\n\nAlternative: 30-Day Government Bill (government_bill_30d).\n\nThis is also eligible, with the same 30-day term and the same EUR 3,000 forecast-based maximum (minimum EUR 1,000). It offers a lower rate of 2.6% annualized, so it is included only if you prefer the government-bill instrument over a bank deposit for the same horizon.\n\nOffers not recommended: The 60-day deposit, 90-day deposit, 90-day government bill, and 60-day corporate commercial paper are all below their minimums under the current forecast (forecast limits of EUR 1,200 or EUR 0), so they are not eligible. The 1-year/2-"
    }
}
```

# Przykłady responsów

```json
{
    "account_id": "account",
    "as_of": "2026-11-21",
    "families": [
        {
            "family_id": "term_deposit",
            "family_name": "Term Deposit",
            "recommended_offer_id": "deposit_30d",
            "reason": "Highest short-term rate among 30-day options (3.5% annualized) with a flexible \u20ac1,000\u2013\u20ac3,000 limit and the shortest lockup, fitting a near-term cash forecast where waiting longer adds little benefit.",
            "variants": [
                {
                    "offer_id": "deposit_30d",
                    "name": "30-day Term Deposit",
                    "term_days": 30,
                    "currency": "EUR",
                    "min_amount": "1000.00",
                    "max_amount": "3000.00",
                    "annual_rate_pct": 3.5
                },
                {
                    "offer_id": "deposit_60d",
                    "name": "60-day Term Deposit",
                    "term_days": 60,
                    "currency": "EUR",
                    "min_amount": "1500.00",
                    "max_amount": "2500.00",
                    "annual_rate_pct": 3.8
                },
                {
                    "offer_id": "deposit_90d",
                    "name": "90-day Term Deposit",
                    "term_days": 90,
                    "currency": "EUR",
                    "min_amount": "2000.00",
                    "max_amount": "2000.00",
                    "annual_rate_pct": 4.2
                }
            ]
        },
        {
            "family_id": "agency_note",
            "family_name": "Public Agency Note",
            "recommended_offer_id": "agency_note_30d",
            "reason": "Meaningful trade-off: a 3.4% 30-day rate with the same \u20ac1,000\u2013\u20ac3,000 limit, offering a different issuer profile (public agency) while keeping the short lockup.",
            "variants": [
                {
                    "offer_id": "agency_note_30d",
                    "name": "30-day Public Agency Note",
                    "term_days": 30,
                    "currency": "EUR",
                    "min_amount": "1000.00",
                    "max_amount": "3000.00",
                    "annual_rate_pct": 3.4
                },
                {
                    "offer_id": "agency_note_60d",
                    "name": "60-day Public Agency Note",
                    "term_days": 60,
                    "currency": "EUR",
                    "min_amount": "1500.00",
                    "max_amount": "2500.00",
                    "annual_rate_pct": 3.9
                },
                {
                    "offer_id": "agency_note_90d",
                    "name": "90-day Public Agency Note",
                    "term_days": 90,
                    "currency": "EUR",
                    "min_amount": "2000.00",
                    "max_amount": "2000.00",
                    "annual_rate_pct": 4.0
                }
            ]
        },
        {
            "family_id": "covered_bank_note",
            "family_name": "Covered Bank Note",
            "recommended_offer_id": "covered_bank_note_30d",
            "reason": "Different amount-limit trade-off: a higher 3.6% 30-day rate but a tighter \u20ac2,500\u2013\u20ac3,000 window, useful if the forecast supports committing the full upper band.",
            "variants": [
                {
                    "offer_id": "covered_bank_note_30d",
                    "name": "30-day Covered Bank Note",
                    "term_days": 30,
                    "currency": "EUR",
                    "min_amount": "2500.00",
                    "max_amount": "3000.00",
                    "annual_rate_pct": 3.6
                },
                {
                    "offer_id": "covered_bank_note_60d",
                    "name": "60-day Covered Bank Note",
                    "term_days": 60,
                    "currency": "EUR",
                    "min_amount": "2500.00",
                    "max_amount": "2500.00",
                    "annual_rate_pct": 4.0
                }
            ]
        }
    ],
    "notification": {
        "subject": "Recommended 30-day cash options for your forecast",
        "body": "Based on the current forecast, I recommend considering these 30-day options, each drawing from the same cash and to be evaluated individually:\n\n1. 30-day Term Deposit (deposit_30d): 3.5% annualized, forecast-based limit \u20ac1,000\u2013\u20ac3,000. Strongest short-term rate with the shortest lockup.\n2. 30-day Public Agency Note (agency_note_30d): 3.4% annualized, forecast-based limit \u20ac1,000\u2013\u20ac3,000. Similar term and limit with a different issuer profile.\n3. 30-day Covered Bank Note (covered_bank_note_30d): 3.6% annualized, forecast-based limit \u20ac2,500\u2013\u20ac3,000. Higher rate but a narrower amount window.\n\nPlease compare the eligible durations for each family in the app before deciding."
    }
}
```

```json
{
    "account_id": "account",
    "as_of": "2026-11-21",
    "families": [
        {
            "family_id": "term_deposit",
            "family_name": "Term Deposit",
            "recommended_offer_id": "deposit_45d",
            "reason": "Highest stated annualized rate (3.7%) among eligible options. The 45-day lockup is acceptable if the forecast supports keeping the full \u20ac1,000 limit idle for that period; the app will also show the 14-day variant if a shorter term is preferred.",
            "variants": [
                {
                    "offer_id": "deposit_14d",
                    "name": "14-day Term Deposit",
                    "term_days": 14,
                    "currency": "EUR",
                    "min_amount": "500.00",
                    "max_amount": "1500.00",
                    "annual_rate_pct": 2.8
                },
                {
                    "offer_id": "deposit_45d",
                    "name": "45-day Term Deposit",
                    "term_days": 45,
                    "currency": "EUR",
                    "min_amount": "1000.00",
                    "max_amount": "1000.00",
                    "annual_rate_pct": 3.7
                }
            ]
        },
        {
            "family_id": "bank_certificate",
            "family_name": "Bank Certificate",
            "recommended_offer_id": "bank_certificate_45d",
            "reason": "Meaningful trade-off: a different product family with a lower rate (3.3%) but a lower minimum (\u20ac500) and a \u20ac1,000 cap, useful if the forecast amount is closer to \u20ac500\u2013\u20ac1,000 or if diversifying across product types is desired.",
            "variants": [
                {
                    "offer_id": "bank_certificate_45d",
                    "name": "45-day Bank Certificate",
                    "term_days": 45,
                    "currency": "EUR",
                    "min_amount": "500.00",
                    "max_amount": "1000.00",
                    "annual_rate_pct": 3.3
                }
            ]
        }
    ],
    "notification": {
        "subject": "Eligible deposit options for your forecast",
        "body": "Hi,\n\nBased on the current forecast, here are the eligible options to consider (each draws from the same cash and should be evaluated individually):\n\n1. Term Deposit \u2013 45-day (deposit_45d): up to \u20ac1,000 at 3.7% annualized. This is the strongest rate available; the 45-day lockup fits if the forecast supports keeping the full amount idle for that period.\n2. Bank Certificate \u2013 45-day (bank_certificate_45d): \u20ac500\u2013\u20ac1,000 at 3.3% annualized. A different product family with a lower minimum, useful if the forecast amount is nearer the lower end or if you prefer diversification.\n\nThe amounts above are forecast-based limits, not commitments. Please compare the eligible durations for each family in the app before deciding.\n\nBest regards"
    }
}
```

```json
{
    "account_id": "account",
    "as_of": "2026-11-21",
    "families": [
        {
            "family_id": "bank_certificate",
            "family_name": "Bank Certificate",
            "recommended_offer_id": "bank_certificate_90d",
            "reason": "Highest stated annualized rate at 3.6%, with the lowest minimum (EUR 500) and a 90-day lockup that matches the short forecast horizon.",
            "variants": [
                {
                    "offer_id": "bank_certificate_90d",
                    "name": "90-day Bank Certificate",
                    "term_days": 90,
                    "currency": "EUR",
                    "min_amount": "500.00",
                    "max_amount": "1500.00",
                    "annual_rate_pct": 3.6
                }
            ]
        },
        {
            "family_id": "supranational_note",
            "family_name": "Supranational Note",
            "recommended_offer_id": "supranational_note_90d",
            "reason": "Same 3.6% rate and 90-day term, but a higher EUR 1,000 minimum; a meaningful alternative if the recipient prefers supranational exposure over a bank certificate.",
            "variants": [
                {
                    "offer_id": "supranational_note_90d",
                    "name": "90-day Supranational Note",
                    "term_days": 90,
                    "currency": "EUR",
                    "min_amount": "1000.00",
                    "max_amount": "1500.00",
                    "annual_rate_pct": 3.6
                }
            ]
        },
        {
            "family_id": "government_bill",
            "family_name": "Government Bill",
            "recommended_offer_id": "government_bill_90d",
            "reason": "Lower 3.1% rate but government-bill backing; included only as a lower-yield, potentially lower-risk trade-off at the same 90-day lockup.",
            "variants": [
                {
                    "offer_id": "government_bill_90d",
                    "name": "90-day Government Bill",
                    "term_days": 90,
                    "currency": "EUR",
                    "min_amount": "1000.00",
                    "max_amount": "1500.00",
                    "annual_rate_pct": 3.1
                }
            ]
        }
    ],
    "notification": {
        "subject": "Recommended 90-day cash options for your forecast",
        "body": "Hi,\n\nBased on the current forecast, here are the product families worth considering (each draws from the same cash and should be evaluated individually):\n\n1. Bank Certificate \u2013 90-day: best stated annualized rate at 3.6%, with a forecast-based limit of up to EUR 1,500 (minimum EUR 500).\n2. Supranational Note \u2013 90-day: same 3.6% rate and 90-day lockup, forecast-based limit up to EUR 1,500 (minimum EUR 1,000); a different issuer profile.\n3. Government Bill \u2013 90-day: lower 3.1% rate, forecast-based limit up to EUR 1,500 (minimum EUR 1,000); a lower-yield, government-backed alternative.\n\nAll three carry a 90-day lockup, which fits the short forecast horizon. Please compare the eligible durations and amounts for each family in the app before deciding.\n\nBest regards"
    }
}
```