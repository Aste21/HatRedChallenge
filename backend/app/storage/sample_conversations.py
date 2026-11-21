"""Curated sample conversations that show a new account what the assistant can do.

Every figure quoted below was computed from the account's bank statement (see `data/raw/`), not estimated;
figures that are not from the bank data are labelled illustrative. The samples are inserted once per
account (tracked in the `sample_seeds` table), so a sample the owner deletes stays deleted.

Re-seed an account for a demo (deletes all of its conversations first):
    python -m app.storage.sample_conversations --reset amalfi
"""

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from app.agents.chat.charts import ChartSpec
from app.storage.conversations import (
    ConversationDraft,
    ConversationRepository,
    StoredMessage,
    _to_iso,
    get_conversation_repository,
)

# Time between a question and the answer, and between two exchanges, so the history reads naturally.
REPLY_DELAY = timedelta(seconds=25)
EXCHANGE_GAP = timedelta(minutes=3)


class SampleExchange(BaseModel):
    """One question from the owner and the assistant's answer, optionally with a chart."""

    question: str
    reply: str
    chart: ChartSpec | None = None


class SampleConversation(BaseModel):
    """A sample conversation and how long ago it started, which sets its place in the history list."""

    title: str
    started_ago: timedelta
    exchanges: list[SampleExchange] = Field(min_length=1)


JUNE_SHUTDOWN = SampleConversation(
    title="June shutdown and the overdraft",
    started_ago=timedelta(minutes=50),
    exchanges=[
        SampleExchange(
            question="What happened in June 2025?",
            reply=(
                "June was the toughest month of the year, Vincenzo. The pizzeria was closed for the summer "
                "holiday, so **no money came in at all in June**, while the fixed costs kept going out.\n\n"
                "**What left the account in June: €22,105.00**\n"
                "- Net salaries for the team: €8,600.00\n"
                "- Zurich partnership tranche: €4,375.00 (4,166.67 CHF at 1.050 EUR/CHF, the highest rate "
                "of the year)\n"
                "- Rent: €3,800.00\n"
                "- Social security: €2,650.00\n"
                "- Income tax prepayment: €1,150.00\n"
                "- Wage tax: €880.00\n"
                "- Energy: €650.00\n\n"
                "**What it did to your balance**\n"
                "- You started June with €2,006.31 (balance on 31 May).\n"
                "- The account went into overdraft on 1 June, when the rent was paid, and ended June at "
                "−€20,098.69.\n"
                "- The lowest point was **−€22,097.60 on 3 July 2025**, just after July's rent, while "
                "takings were only starting again.\n"
                "- Strong summer takings brought it back: the balance has stayed positive since "
                "5 September 2025.\n\n"
                "The chart shows your daily balance from May to August."
            ),
            chart=ChartSpec(
                title="Daily balance, May to August 2025",
                metrics=["balance"],
                chart_type="area",
                granularity="day",
                start_month="2025-05",
                end_month="2025-08",
            ),
        ),
        SampleExchange(
            question="Show me money in and out around the summer",
            reply=(
                "Here are May to September side by side:\n\n"
                "- **May:** €45,540.03 in, €45,912.85 out\n"
                "- **June:** €0.00 in, €22,105.00 out\n"
                "- **July:** €52,550.85 in, €43,767.29 out\n"
                "- **August:** €55,016.99 in, €45,441.11 out\n"
                "- **September:** €55,498.99 in, €45,191.67 out\n\n"
                "After reopening, July to September each brought in between €8,783.56 and €10,307.32 more "
                "than went out. That surplus is what slowly filled the June gap again."
            ),
            chart=ChartSpec(
                title="Money in and out, May to September",
                metrics=["money_in", "money_out"],
                chart_type="bar",
                granularity="month",
                start_month="2025-05",
                end_month="2025-09",
            ),
        ),
        SampleExchange(
            question="How could I avoid that next year?",
            reply=(
                "Here are three options you could consider. They are proposals only: nothing happens unless "
                "you decide to go ahead.\n\n"
                "**1. Arrange a credit line in May, before the closure**\n"
                "- The deepest dip was €22,097.60, so a facility of about €25,000 would have covered it "
                "with some room to spare.\n"
                "- Arranged in advance, it is usually calmer and cheaper than an unplanned overdraft. "
                "Amounts and terms here are illustrative; your bank would quote real ones.\n\n"
                "**2. Keep a summer reserve from the strong months**\n"
                "- January to May together ended at −€493.69, so the first months of the year do not "
                "build a buffer on their own. July to December added €53,365.03.\n"
                "- You closed 2025 with €33,266.34. Setting about €22,500 of it aside until after the "
                "summer would cover a June like this year's (€22,105.00 of costs with no takings).\n\n"
                "**3. Plan big payments around the closure**\n"
                "- The Zurich tranche (€4,375.00 on 15 June) and the income tax prepayment (€1,150.00 on "
                "10 June) both fell into the closed month.\n"
                "- All 12 Zurich tranches were paid in 2025, so none are due in 2026. That alone removes "
                "about €4,350 a month. If you agree similar payments in future, dates outside June would "
                "help.\n\n"
                "You can review proposals like these on the **Proposals** page. If you approve one, it is "
                "recorded as a simulated step and you get a confirmation; nothing is sent to a real bank."
            ),
        ),
    ],
)

YEAR_OVERVIEW = SampleConversation(
    title="How 2025 went overall",
    started_ago=timedelta(hours=3, minutes=10),
    exchanges=[
        SampleExchange(
            question="How did the year go overall?",
            reply=(
                "Overall, 2025 ended well, Vincenzo, with one big dip in the middle.\n\n"
                "**The year in numbers**\n"
                "- Money in: €544,424.27, all of it card takings (€435,319.19 by credit card, €109,105.08 "
                "by debit card)\n"
                "- Money out: €513,657.93\n"
                "- Net result: **+€30,766.34**\n"
                "- Balance: from €2,500.00 on 1 January to **€33,266.34** on 31 December\n\n"
                "**Strongest and weakest months**\n"
                "- Best month: September, with €55,498.99 in and +€10,307.32 net.\n"
                "- Weakest month: June, the holiday closure, with no takings and −€22,105.00 net.\n"
                "- January to May was roughly break-even (−€493.69 together), while July to December "
                "added +€53,365.03.\n\n"
                "The chart compares money in and money out for every month."
            ),
            chart=ChartSpec(
                title="Money in and out per month, 2025",
                metrics=["money_in", "money_out"],
                chart_type="bar",
                granularity="month",
                start_month="2025-01",
                end_month="2025-12",
            ),
        ),
        SampleExchange(
            question="What could I do with the money that's left?",
            reply=(
                "You have €33,266.34 on the account. Here is one way to think about it; the decision is "
                "yours.\n\n"
                "**First, keep enough for everyday bills**\n"
                "- Your regular monthly bills are €16,580.00: rent €3,800.00, net salaries €8,600.00, "
                "social security €2,650.00, wage tax €880.00 and energy €650.00.\n"
                "- Keeping about one month of these on the account covers normal ups and downs.\n\n"
                "**Then, options for the rest (about €16,700)**\n"
                "- **Fixed-term deposit:** the money is locked for an agreed time and earns a fixed rate. "
                "With an illustrative rate of 2% a year, €15,000 for five months would earn about €125. "
                "Ending it in late May would make it your summer reserve.\n"
                "- **Money market fund:** usually available at short notice, but its value can move a "
                "little.\n"
                "- **Financing an investment:** if you plan a bigger purchase, such as a new oven, "
                "financing it instead of paying cash keeps your reserve intact.\n\n"
                "Rates and products here are illustrative, not offers. The **Proposals** page shows "
                "concrete suggestions you can approve or decline."
            ),
        ),
    ],
)

TEAM_AND_PAYROLL = SampleConversation(
    title="Team and payroll costs",
    started_ago=timedelta(hours=21, minutes=40),
    exchanges=[
        SampleExchange(
            question="Who works at the pizzeria and what does payroll cost?",
            reply=(
                "Four people are on the payroll, including you:\n\n"
                "- **Vincenzo Amalfi**, owner: €3,200.00 net per month\n"
                "- **Yusuf Akcit**, pizza baker: €2,350.00\n"
                "- **Rosa Pavese**, chef: €2,100.00\n"
                "- **Vanessa Paradi**, waitstaff (temporary): €950.00\n\n"
                "Together that is **€8,600.00 in net pay per month**, paid on the 28th, or €103,200.00 "
                "for 2025.\n\n"
                "**On top of net pay, the business pays every month:**\n"
                "- Social security (Techniker Krankenkasse): €2,650.00 on the 27th\n"
                "- Wage tax and solidarity surcharge: €880.00 on the 10th\n\n"
                "So the team costs **€12,130.00 per month**, or €145,560.00 in 2025. That is 28% of "
                "everything that left the account. The chart shows each person's net pay for the year."
            ),
            chart=ChartSpec(
                title="Net pay per person in 2025",
                metrics=["payroll_by_employee"],
                start_month="2025-01",
                end_month="2025-12",
            ),
        ),
        SampleExchange(
            question="And per month?",
            reply=(
                "Net payroll was exactly **€8,600.00 in every month of 2025**, so the chart shows twelve "
                "equal bars.\n\n"
                "That includes June: the pizzeria was closed and took no money, but everyone was still paid "
                "in full. Payroll is a fixed cost that does not shrink when takings do, which is why it "
                "matters so much for planning a closure."
            ),
            chart=ChartSpec(
                title="Net payroll per month, 2025",
                metrics=["payroll"],
                chart_type="bar",
                granularity="month",
                start_month="2025-01",
                end_month="2025-12",
            ),
        ),
        SampleExchange(
            question="How does that compare to what comes in?",
            reply=(
                "In an open month, net payroll took **about 17% of your takings** on average (€8,600.00 "
                "against €49,493.12 average money in, June left out).\n\n"
                "- Highest share: February, 20.5% (€42,011.43 in).\n"
                "- Lowest share: September, 15.5% (€55,498.99 in).\n"
                "- In June there were no takings at all, so payroll had to come entirely from the "
                "account.\n\n"
                "The busier second half of the year made the same payroll noticeably easier to carry."
            ),
            chart=ChartSpec(
                title="Payroll compared with money in",
                metrics=["money_in", "payroll"],
                chart_type="bar",
                granularity="month",
                start_month="2025-01",
                end_month="2025-12",
            ),
        ),
    ],
)

ZURICH_PARTNERSHIP = SampleConversation(
    title="The monthly payment to Zurich",
    started_ago=timedelta(days=1, hours=4),
    exchanges=[
        SampleExchange(
            question="Explain the payment to Zurich every month",
            reply=(
                "That is your **silent partnership** in your brother Luigi's new restaurant in Zurich.\n\n"
                "- You agreed to invest **50,000 CHF**, paid in 12 monthly tranches of 4,166.67 CHF on the "
                "15th.\n"
                "- All 12 tranches were paid in 2025, so the commitment is complete and none are due in "
                "2026.\n"
                "- The payments are in Swiss francs, so the bank converted each one at that day's exchange "
                "rate. The rate is shown in every payment reference.\n\n"
                "**What it cost in euros**\n"
                "- In total you paid **€52,179.21**, on average about €1.04 for each Swiss franc.\n"
                "- The cheapest tranche was €4,325.00 in March (1.038 EUR/CHF).\n"
                "- The most expensive was €4,375.00 in June (1.050 EUR/CHF), right in the month the "
                "pizzeria was closed."
            ),
        ),
        SampleExchange(
            question="What does exchange rate risk mean for me?",
            reply=(
                "In simple words: you owed a fixed amount in Swiss francs but paid from a euro account, so "
                "the euro price of each payment was only known on the day it left.\n\n"
                "- In 2025 the rate moved between 1.038 and 1.050. That made a €50.00 difference between "
                "the cheapest and the most expensive tranche.\n"
                "- On 50,000 CHF, every change of 0.01 in the rate means about €500 more or less.\n\n"
                "**If you make similar payments in future, you could consider:**\n"
                "- Agreeing the amount in euros, so the cost is known in advance.\n"
                "- Fixing the exchange rate with your bank ahead of planned payments. Terms are "
                "illustrative; your bank would quote real ones.\n"
                "- If the Zurich restaurant ever pays you a share of its profits in francs, the same "
                "effect works the other way round.\n\n"
                "Right now there is no open currency exposure: the partnership is fully paid."
            ),
        ),
    ],
)

WHERE_THE_MONEY_GOES = SampleConversation(
    title="Where the money goes",
    started_ago=timedelta(days=2, hours=6),
    exchanges=[
        SampleExchange(
            question="Where does my money go?",
            reply=(
                "In 2025, €513,657.93 left the account. From largest to smallest:\n\n"
                "- Staff salaries: €103,200.00 (20.1%)\n"
                "- Food supplies (Asimex Wholesale): €91,576.40 (17.8%)\n"
                "- Wine and drinks (Fattoria La Vino): €88,616.66 (17.3%)\n"
                "- Fresh produce (Central Wholesale Market): €76,825.66 (15.0%)\n"
                "- Zurich partnership: €52,179.21 (10.2%)\n"
                "- Rent: €45,600.00 (8.9%)\n"
                "- Social security: €31,800.00 (6.2%)\n"
                "- Taxes: €16,060.00 (3.1%)\n"
                "- Energy: €7,800.00 (1.5%)\n\n"
                "Food, wine and fresh produce together cost **€257,018.72**: half of all spending, and 47% "
                "of your takings."
            ),
            chart=ChartSpec(title="Money out by category, 2025", metrics=["spending_by_category"]),
        ),
        SampleExchange(
            question="Which of these can I actually influence?",
            reply=(
                "Roughly, your costs fall into two groups.\n\n"
                "**Fixed: hard to change quickly (€204,460.00, 40%)**\n"
                "- Salaries, rent, social security, taxes and energy. They are paid every month, open or "
                "closed.\n\n"
                "**Variable: move with how busy you are (€257,018.72, 50%)**\n"
                "- Food, wine and fresh produce. Comparing supplier prices or agreeing volume terms is "
                "where you have the most room. As an illustration, 3% lower purchase prices would have "
                "saved about €7,710 in 2025.\n\n"
                "**Finished: the Zurich partnership (€52,179.21, 10%)**\n"
                "- All tranches are paid, so this money stays with the business from 2026 on.\n\n"
                "These are ideas to weigh up, not instructions; you know your suppliers best."
            ),
        ),
        SampleExchange(
            question="And which days bring in the most money?",
            reply=(
                "Your weekends are clearly the busiest. Average debit-card takings per open day:\n\n"
                "- Monday to Thursday: about €284 to €286\n"
                "- Friday to Sunday: about €380 to €382\n\n"
                "That is roughly a third more from Friday to Sunday. Credit-card takings are paid out in "
                "batches twice a week, so the chart uses debit cards, which are settled every day."
            ),
            chart=ChartSpec(title="Average card takings by weekday", metrics=["takings_by_weekday"]),
        ),
    ],
)

# Per account, in the order shown in the history list (newest first).
SAMPLE_CONVERSATIONS: dict[str, list[SampleConversation]] = {
    "amalfi": [JUNE_SHUTDOWN, YEAR_OVERVIEW, TEAM_AND_PAYROLL, ZURICH_PARTNERSHIP, WHERE_THE_MONEY_GOES],
}


def build_sample_drafts(account_id: str, now: datetime) -> list[ConversationDraft]:
    """Turn the account's sample conversations into dated drafts for the repository.

    Args:
        account_id: The account whose samples are built.
        now: Current UTC time; every sample is dated in the recent past relative to it.

    Returns:
        The drafts, or an empty list when the account has no samples.

    Steps:
        1. Start each conversation `started_ago` before `now`.
        2. Date each question `EXCHANGE_GAP` after the previous one and its answer `REPLY_DELAY` later.
    """
    drafts = []
    for sample in SAMPLE_CONVERSATIONS.get(account_id, []):
        started_at = now - sample.started_ago
        messages = []
        for exchange_index, exchange in enumerate(sample.exchanges):
            asked_at = started_at + exchange_index * EXCHANGE_GAP
            messages.append(
                StoredMessage(role="user", content=exchange.question, created_at=_to_iso(asked_at))
            )
            messages.append(
                StoredMessage(
                    role="assistant",
                    content=exchange.reply,
                    created_at=_to_iso(asked_at + REPLY_DELAY),
                    chart=exchange.chart,
                )
            )
        drafts.append(ConversationDraft(title=sample.title, messages=messages))
    return drafts


def seed_sample_conversations(repository: ConversationRepository) -> list[str]:
    """Insert the sample conversations for every account that has never been seeded.

    Args:
        repository: The chat history store.

    Returns:
        The ids of the accounts that were seeded now.

    Steps:
        1. Build the drafts for each account with samples, dated relative to now.
        2. Let the repository insert them unless the account was seeded before.
    """
    now = datetime.now(UTC)
    return [
        account_id
        for account_id in SAMPLE_CONVERSATIONS
        if repository.seed_conversations(account_id, build_sample_drafts(account_id, now))
    ]


def main() -> None:
    """Command line entry point: seed new accounts, or reset accounts to the samples for a demo.

    Steps:
        1. Parse `--reset ACCOUNT_ID` (repeatable) and an optional `--database` path.
        2. Reset the named accounts (all their conversations are replaced), or seed unseeded accounts.
        3. Print what was done.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--reset",
        action="append",
        default=[],
        metavar="ACCOUNT_ID",
        choices=sorted(SAMPLE_CONVERSATIONS),
        help="delete the account's conversations and insert the samples fresh",
    )
    parser.add_argument("--database", type=Path, help="SQLite file (default: the configured database_path)")
    arguments = parser.parse_args()
    repository = (
        ConversationRepository(arguments.database) if arguments.database else get_conversation_repository()
    )
    if arguments.reset:
        now = datetime.now(UTC)
        for account_id in arguments.reset:
            drafts = build_sample_drafts(account_id, now)
            repository.reset_conversations(account_id, drafts)
            print(f"Reset {account_id}: {len(drafts)} sample conversations")
        return
    seeded_accounts = seed_sample_conversations(repository)
    print(f"Seeded: {', '.join(seeded_accounts)}" if seeded_accounts else "All accounts already seeded")


if __name__ == "__main__":
    main()
