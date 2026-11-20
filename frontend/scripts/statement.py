"""Build the dashboard's aggregate demo data from the team's 2025 statement."""
import csv
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

frontend = Path(__file__).resolve().parents[1]
source = frontend.parent / "data/raw/pizzeria-amalfi-bank-statement-2025-v6.csv"
days = defaultdict(lambda: [0, 0])
with source.open(encoding="utf-8-sig", newline="") as stream:
    for row in csv.DictReader(stream, delimiter=";"):
        day = datetime.strptime(row["Booking Date"], "%d.%m.%y").date()
        amount = Decimal(row["Amount"].replace(",", "."))
        if row["Currency"] == "CHF":
            rate = re.search(r"@ ([\d.]+) EUR/CHF", row["Payment Reference"])
            if not rate:
                raise ValueError("Missing CHF exchange rate")
            amount *= Decimal(rate[1])
        elif row["Currency"] != "EUR":
            raise ValueError("Unsupported currency")
        days[day][0 if amount > 0 else 1] += abs(amount) * 100

def nearest_cent(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


income_total = costs_total = Decimal(0)
history = []
for offset in range(365):
    day = date(2025, 1, 1) + timedelta(days=offset)
    income, costs = days[day]
    old_income, old_costs = nearest_cent(income_total), nearest_cent(costs_total)
    income_total += income
    costs_total += costs
    balance = 250000 + nearest_cent(income_total - costs_total)
    history.append(dict(date=day.isoformat(), balance=balance,
                        income=nearest_cent(income_total) - old_income,
                        costs=nearest_cent(costs_total) - old_costs))

# Illustrative January stress scenario: continue known fixed bills, assume zero receipts.
schedule = [(1, "Rent", 380000), (10, "Wage tax", 88000), (10, "Energy", 65000),
            (27, "Social security", 265000), (28, "Payroll", 860000)]
scenario = []
remaining = balance
for day in range(1, 32):
    remaining -= sum(cents for payment_day, _, cents in schedule if day == payment_day)
    scenario.append(dict(date=date(2026, 1, day).isoformat(), balance=remaining))

output = frontend / "src/lib/statement.json"
output.write_text(json.dumps(dict(history=history, scenario=scenario, bills=schedule),
                             separators=(",", ":")) + "\n", encoding="utf-8")
