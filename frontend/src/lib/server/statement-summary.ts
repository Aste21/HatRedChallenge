import { createLedger, dateLabel, money, type Statement } from '#lib/ledger.ts';

/**
 * The bank-statement figures the assistant may quote, as compact text. Computed here because the
 * statement lives in the frontend; the assistant only repeats these numbers, it never computes its own.
 */
export function statementSummary(statement: Statement): string {
  const ledger = createLedger(statement);
  const totalIn = ledger.months.reduce((sum, month) => sum + month.income, 0);
  const totalOut = ledger.months.reduce((sum, month) => sum + month.costs, 0);
  const payrollTotal = ledger.payroll.reduce(
    (sum, person) => sum + person.payments.reduce((personSum, payment) => personSum + payment.cents, 0),
    0
  );
  return [
    `Bank statement ${dateLabel(ledger.history[0].date)} to ${dateLabel(ledger.closing.date)}.`,
    `Closing balance ${money(ledger.closing.balance)} on ${dateLabel(ledger.closing.date)}. ` +
      `Lowest daily balance ${money(ledger.lowest.balance)} on ${dateLabel(ledger.lowest.date)}.`,
    `Whole period: money in ${money(totalIn)}, money out ${money(totalOut)}, net ${money(totalIn - totalOut)}.`,
    'Per month (money in / money out / net / closing balance):',
    ...ledger.months.map(
      (month) => `${month.name}: ${money(month.income)} / ${money(month.costs)} / ${money(month.income - month.costs)} / ${money(month.balance)}`
    ),
    'Money out by category: ' + ledger.spending.map((row) => `${row.name} ${money(row.cents)}`).join('; ') + '.',
    `Net salaries paid in the period: ${money(payrollTotal)}.`
  ].join('\n');
}
