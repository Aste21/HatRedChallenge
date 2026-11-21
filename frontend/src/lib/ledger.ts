import sample from './statement.json';

export const { history, scenario } = sample;
/** Money out in 2025 by category, in cents, largest first (CHF converted at the rate in the reference). */
export const spending = sample.spending.map(([name, cents]) => ({ name: String(name), cents: Number(cents) }));
export const closing = history[history.length - 1];
export const lowest = history.reduce((a, b) => a.balance < b.balance ? a : b);
export const bills = sample.bills.map(([day, name, cents]) => ({ day: Number(day), name: String(name), cents: Number(cents) }));
export const reserve = bills.reduce((sum, bill) => sum + bill.cents, 0);
export const money = (cents: number) => new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(cents / 100);
export const dateLabel = (iso: string, long = false) => new Intl.DateTimeFormat('en-GB', {
  day: 'numeric', month: long ? 'long' : 'short', year: 'numeric', timeZone: 'UTC'
}).format(new Date(iso));
/** Average daily debit-card takings per weekday in cents, Monday first. */
export const weekdayTakings = sample.weekdays.map(Number);
export const months = Array.from({ length: 12 }, (_, index) => {
  const rows = history.filter(day => Number(day.date.slice(5, 7)) === index + 1);
  return { name: new Intl.DateTimeFormat('en-GB', { month: 'long', timeZone: 'UTC' }).format(new Date(rows[0].date)),
    income: rows.reduce((sum, day) => sum + day.income, 0), costs: rows.reduce((sum, day) => sum + day.costs, 0),
    balance: rows[rows.length - 1].balance };
});
export const december = months[11];
