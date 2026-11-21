import { getContext, setContext } from 'svelte';

/** Aggregated bank statement of one account, as built by `scripts/statement.py` (amounts in cents). */
export type Statement = {
  history: { date: string; balance: number; income: number; costs: number }[];
  scenario: { date: string; balance: number }[];
  bills: (string | number)[][];
  spending: (string | number)[][];
  weekdays: number[];
};

export const money = (cents: number) => new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(cents / 100);
export const dateLabel = (iso: string, long = false) => new Intl.DateTimeFormat('en-GB', {
  day: 'numeric', month: long ? 'long' : 'short', year: 'numeric', timeZone: 'UTC'
}).format(new Date(iso));

/** Derives everything the pages and charts show from one account's statement. */
export function createLedger(statement: Statement) {
  const { history, scenario } = statement;
  const months = Array.from({ length: 12 }, (_, index) => {
    const rows = history.filter((day) => Number(day.date.slice(5, 7)) === index + 1);
    return {
      name: new Intl.DateTimeFormat('en-GB', { month: 'long', timeZone: 'UTC' }).format(new Date(rows[0].date)),
      income: rows.reduce((sum, day) => sum + day.income, 0),
      costs: rows.reduce((sum, day) => sum + day.costs, 0),
      balance: rows[rows.length - 1].balance
    };
  });
  return {
    history,
    scenario,
    months,
    december: months[11],
    closing: history[history.length - 1],
    lowest: history.reduce((first, second) => (first.balance < second.balance ? first : second)),
    bills: statement.bills.map(([day, name, cents]) => ({ day: Number(day), name: String(name), cents: Number(cents) })),
    /** Money out by category, in cents, largest first (CHF converted at the rate in the reference). */
    spending: statement.spending.map(([name, cents]) => ({ name: String(name), cents: Number(cents) })),
    /** Average daily debit-card takings per weekday in cents, Monday first. */
    weekdayTakings: statement.weekdays.map(Number)
  };
}

export type Ledger = ReturnType<typeof createLedger>;

const ledgerKey = Symbol('ledger');

/** Makes the signed-in account's ledger available to every page and chart below the app layout. */
export const provideLedger = (ledger: Ledger) => setContext(ledgerKey, ledger);

export function useLedger(): Ledger {
  const ledger = getContext<Ledger | undefined>(ledgerKey);
  if (!ledger) throw new Error('useLedger() needs the app layout to provide the account ledger.');
  return ledger;
}
