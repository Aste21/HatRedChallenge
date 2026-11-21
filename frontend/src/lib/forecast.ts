/** Shapes returned by the backend's /api/forecast, /api/proposals and /api/news (amounts in EUR, not cents). */

export type ForecastDay = { date: string; p5: number; p50: number; p95: number };

export type SafeToLock = { days: number; amount: number; lowest_balance: number };

/** A checked change to future cash flow derived from news; type-specific fields vary. */
export type ForecastEvent = {
  type: 'shift_amount' | 'one_off' | 'scale' | 'closure';
  certainty: 'official' | 'assumption';
  why: string;
  stream?: string;
  from?: string;
  to?: string | null;
  date?: string;
  change_pct?: number;
  amount?: number;
  flow?: 'sales' | 'costs';
  factor_mean?: number;
};

export type Scenario = {
  events: ForecastEvent[];
  buffer: { amount: number; source: string };
  safe_to_lock: SafeToLock[];
  p_below_zero: number;
  end_balance_p50: number;
  daily: ForecastDay[];
};

export type ScheduledPayment = {
  name: string;
  day: number;
  months: number[] | null;
  amount: number;
  counterparty: string | null;
  last_reference: string | null;
};

export type Forecast = {
  as_of: string;
  start_balance: number;
  schedule: ScheduledPayment[];
  official: Scenario;
  with_assumptions: Scenario;
};

export type ProposalStatus = 'awaiting_approval' | 'approved' | 'declined' | 'superseded';

export type Proposal = {
  id: string;
  kind: 'fixed_term_deposit' | 'credit_line';
  title: string;
  amount: number;
  term_days: number | null;
  annual_rate_pct: number | null;
  min_amount: number | null;
  interest_eur: number | null;
  lowest_balance: number | null;
  buffer_eur: number | null;
  safe_amount: number | null;
  analysis: string;
  recommendation: string;
  rationale: string;
  on_approval: string;
  requires_approval: boolean;
  execution_mode: 'simulated';
  status: ProposalStatus;
  decided_at: string | null;
};

export type ProposalBoard = {
  as_of: string;
  start_balance: number;
  proposals: Proposal[];
  notification_draft: { subject: string; body: string } | null;
  warnings: string[];
};

export type SimulatedTransaction = {
  id: string;
  proposal_id: string;
  kind: string;
  description: string;
  amount: number;
  created_at: string;
};

export type StoredNotification = {
  id: string;
  recipient: string;
  subject: string;
  body: string;
  status: 'queued' | 'sent' | 'failed';
  created_at: string;
};

export type Article = { id: string; title: string; summary: string; source: string; url: string; published: string | null; reason: string };

export type NewsImpact = {
  article_id: string;
  title: string;
  events: ForecastEvent[];
  rejected_count: number;
  created_at: string;
};

/** Formats euros (not cents) the same way as the rest of the UI. */
export const euro = (amount: number) =>
  new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(amount);

export const percent = (share: number) =>
  new Intl.NumberFormat('en-IE', { style: 'percent', maximumFractionDigits: 0 }).format(share);

const shortDate = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(iso));

/** One plain-language line for a forecast event, built only from its own fields. */
export function describeEvent(event: ForecastEvent): string {
  const until = event.to ? ` until ${shortDate(event.to)}` : '';
  switch (event.type) {
    case 'shift_amount':
      return `${event.stream} ${(event.change_pct ?? 0) >= 0 ? 'rises' : 'falls'} by ${Math.abs(event.change_pct ?? 0)} % from ${shortDate(event.from!)}`;
    case 'one_off':
      return `One-off ${(event.amount ?? 0) < 0 ? 'payment' : 'receipt'} of ${euro(Math.abs(event.amount ?? 0))} on ${shortDate(event.date!)}`;
    case 'scale':
      return `${event.flow === 'sales' ? 'Sales' : 'Variable costs'} at about ${Math.round((event.factor_mean ?? 1) * 100)} % of normal from ${shortDate(event.from!)}${until}`;
    case 'closure':
      return `Business closed from ${shortDate(event.from!)}${until}; fixed costs continue`;
  }
}

/** The lowest pessimistic (5th percentile) day of a scenario. */
export const worstDay = (scenario: Scenario) =>
  scenario.daily.reduce((lowest, day) => (day.p5 < lowest.p5 ? day : lowest));

/** Next due date of each scheduled payment within `days` after `asOf`, soonest first. */
export function upcomingPayments(schedule: ScheduledPayment[], asOf: string, days = 31) {
  const start = new Date(asOf + 'T00:00:00Z');
  const due: { date: string; payment: ScheduledPayment }[] = [];
  for (let offset = 1; offset <= days; offset++) {
    const day = new Date(start.getTime() + offset * 86_400_000);
    const lastOfMonth = new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth() + 1, 0)).getUTCDate();
    for (const payment of schedule) {
      const dueDay = Math.min(payment.day, lastOfMonth);
      const inMonth = payment.months === null || payment.months.includes(day.getUTCMonth() + 1);
      if (inMonth && day.getUTCDate() === dueDay) due.push({ date: day.toISOString().slice(0, 10), payment });
    }
  }
  return due;
}

/** A numbered news marker on the balance chart; the number matches the "News in your forecast" list. */
export type ChartMarker = { date: string; number: number; label: string };

/** First day an event changes the cash flow. */
export const eventStart = (event: ForecastEvent) => event.from ?? event.date ?? null;
