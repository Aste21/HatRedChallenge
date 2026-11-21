/**
 * Charts the assistant creates on request. The assistant only picks *what* to show (a `ChartSpec`);
 * every figure is computed here from the account's bank statement, so nothing on screen is invented.
 */
import type { Ledger } from '../ledger';

export const TIME_METRICS = ['balance', 'money_in', 'money_out', 'net_result', 'payroll'] as const;
export const CATEGORY_METRICS = ['spending_by_category', 'takings_by_weekday', 'payroll_by_employee'] as const;
/** Breakdowns computed for the chosen months; the others always cover the whole statement. */
const PERIOD_CATEGORY_METRICS: readonly CategoryMetric[] = ['payroll_by_employee'];
export const CHART_TYPES = ['bar', 'line', 'area'] as const;
export const GRANULARITIES = ['day', 'week', 'month'] as const;

export type TimeMetric = (typeof TIME_METRICS)[number];
export type CategoryMetric = (typeof CATEGORY_METRICS)[number];
export type ChartMetric = TimeMetric | CategoryMetric;
export type ChartType = (typeof CHART_TYPES)[number];
export type Granularity = (typeof GRANULARITIES)[number];

export type ChartSpec = {
  title: string;
  metrics: ChartMetric[];
  chart_type: ChartType;
  granularity: Granularity;
  start_month: string | null;
  end_month: string | null;
};

export const metricLabels: Record<ChartMetric, string> = {
  balance: 'Balance',
  money_in: 'Money in',
  money_out: 'Money out',
  net_result: 'Net result',
  payroll: 'Net payroll',
  spending_by_category: 'Money out by category',
  takings_by_weekday: 'Average card takings',
  payroll_by_employee: 'Net pay'
};

export const metricColors: Record<ChartMetric, string> = {
  balance: 'var(--chart-line)',
  money_in: 'var(--chart-in)',
  money_out: 'var(--chart-out)',
  net_result: 'var(--chart-buffer)',
  payroll: 'var(--chart-out-alt)',
  spending_by_category: 'var(--chart-out)',
  takings_by_weekday: 'var(--chart-in)',
  payroll_by_employee: 'var(--chart-out-alt)'
};

export const chartTypeLabels: Record<ChartType, string> = { bar: 'Bars', line: 'Line', area: 'Area' };
const granularityLabels: Record<Granularity, string> = { day: 'per day', week: 'per week', month: 'per month' };

const includes = <T extends string>(list: readonly T[], value: unknown): value is T => list.includes(value as T);
const monthPattern = /^\d{4}-(0[1-9]|1[0-2])$/;

/** Checks a chart coming from the network or from saved settings; anything malformed becomes `null`. */
export function normaliseSpec(value: unknown): ChartSpec | null {
  if (typeof value !== 'object' || value === null) return null;
  const raw = value as Record<string, unknown>;
  const title = typeof raw.title === 'string' ? raw.title.trim().slice(0, 80) : '';
  const metrics = Array.isArray(raw.metrics) ? [...new Set(raw.metrics.filter((metric) => includes([...TIME_METRICS, ...CATEGORY_METRICS], metric)))] : [];
  if (!title || !metrics.length) return null;
  const breakdown = metrics.find((metric) => includes(CATEGORY_METRICS, metric));
  // Like the backend: months only count for breakdowns that use them, and the range is put in order.
  const usesMonths = !breakdown || PERIOD_CATEGORY_METRICS.includes(breakdown);
  const month = (candidate: unknown) => (usesMonths && typeof candidate === 'string' && monthPattern.test(candidate) ? candidate : null);
  const [startMonth, endMonth] = [month(raw.start_month), month(raw.end_month)];
  const ordered = startMonth && endMonth && startMonth > endMonth;
  return {
    title,
    metrics: breakdown ? [breakdown] : metrics.slice(0, 3),
    chart_type: !breakdown && includes(CHART_TYPES, raw.chart_type) ? raw.chart_type : 'bar',
    granularity: includes(GRANULARITIES, raw.granularity) ? raw.granularity : 'month',
    start_month: ordered ? endMonth : startMonth,
    end_month: ordered ? startMonth : endMonth
  };
}

export const isBreakdown = (spec: ChartSpec) => includes(CATEGORY_METRICS, spec.metrics[0]);

/** A stable key: two charts showing the same thing (whatever their title) share it. */
export const specKey = (spec: ChartSpec) =>
  JSON.stringify([
    spec.metrics,
    isBreakdown(spec) ? [spec.start_month, spec.end_month] : [spec.chart_type, spec.granularity, spec.start_month, spec.end_month]
  ]);

export type Series = { metric: ChartMetric; label: string; color: string; values: number[] };
export type ChartData = {
  kind: 'time' | 'category';
  /** Text under each bar or point. */
  labels: string[];
  /** Longer label for the readout and the table, e.g. "Week of 3 Mar 2025". */
  longLabels: string[];
  series: Series[];
  /** What the figures cover, in words, e.g. "January to June 2025, per month". */
  coverage: string;
};

/** Month and year, e.g. "June 2025". */
const monthName = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(iso));
const dayName = (iso: string, withYear = false) =>
  new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: withYear ? 'numeric' : undefined, timeZone: 'UTC' }).format(new Date(iso));

/** Monday of the ISO week a date falls in. */
function weekStart(iso: string): string {
  const date = new Date(iso);
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return date.toISOString().slice(0, 10);
}

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

/** Computes the figures of a chart from the ledger, in cents. */
export function buildChartData(ledger: Ledger, spec: ChartSpec): ChartData {
  const first = ledger.history[0].date;
  const last = ledger.history[ledger.history.length - 1].date;
  const wholePeriod = `${monthName(first)} to ${monthName(last)}`;
  const inMonths = (iso: string) => {
    const month = iso.slice(0, 7);
    return (!spec.start_month || month >= spec.start_month) && (!spec.end_month || month <= spec.end_month);
  };

  if (spec.metrics[0] === 'spending_by_category') {
    return {
      kind: 'category',
      labels: ledger.spending.map((row) => row.name),
      longLabels: ledger.spending.map((row) => row.name),
      series: [{ metric: 'spending_by_category', label: metricLabels.spending_by_category, color: metricColors.spending_by_category, values: ledger.spending.map((row) => row.cents) }],
      coverage: `All payments out, ${wholePeriod}`
    };
  }
  if (spec.metrics[0] === 'takings_by_weekday') {
    return {
      kind: 'category',
      labels: WEEKDAYS,
      longLabels: WEEKDAYS,
      series: [{ metric: 'takings_by_weekday', label: metricLabels.takings_by_weekday, color: metricColors.takings_by_weekday, values: ledger.weekdayTakings }],
      coverage: `Average debit-card takings per day, ${wholePeriod}`
    };
  }
  if (spec.metrics[0] === 'payroll_by_employee') {
    const staff = ledger.payroll
      .map((person) => ({ ...person, payments: person.payments.filter((payment) => inMonths(payment.date)) }))
      .filter((person) => person.payments.length);
    const paydays = new Set(staff.flatMap((person) => person.payments.map((payment) => payment.date)));
    const range = [...paydays].sort();
    return {
      kind: 'category',
      labels: staff.map((person) => `${person.name} · ${person.role}`),
      longLabels: staff.map((person) => `${person.name} · ${person.role}`),
      series: [{
        metric: 'payroll_by_employee',
        label: metricLabels.payroll_by_employee,
        color: metricColors.payroll_by_employee,
        values: staff.map((person) => person.payments.reduce((sum, payment) => sum + payment.cents, 0))
      }],
      coverage: range.length
        ? `Net salaries paid per person, ${monthName(range[0])} to ${monthName(range[range.length - 1])} (${paydays.size} ${paydays.size === 1 ? 'payday' : 'paydays'})`
        : 'No salary payments in the chosen months'
    };
  }

  const days = ledger.history.filter((day) => inMonths(day.date));
  const payrollByDay = new Map<string, number>();
  for (const payment of ledger.payroll.flatMap((person) => person.payments)) {
    payrollByDay.set(payment.date, (payrollByDay.get(payment.date) ?? 0) + payment.cents);
  }
  const groupKey = (iso: string) => (spec.granularity === 'month' ? iso.slice(0, 7) : spec.granularity === 'week' ? weekStart(iso) : iso);
  const groups: { key: string; first: string; days: typeof days }[] = [];
  for (const day of days) {
    const key = groupKey(day.date);
    if (groups.at(-1)?.key === key) groups.at(-1)!.days.push(day);
    else groups.push({ key, first: day.date, days: [day] });
  }
  const valueOf = (metric: TimeMetric, group: (typeof groups)[number]) => {
    const income = group.days.reduce((sum, day) => sum + day.income, 0);
    const costs = group.days.reduce((sum, day) => sum + day.costs, 0);
    if (metric === 'balance') return group.days[group.days.length - 1].balance;
    if (metric === 'payroll') return group.days.reduce((sum, day) => sum + (payrollByDay.get(day.date) ?? 0), 0);
    return metric === 'money_in' ? income : metric === 'money_out' ? costs : income - costs;
  };
  const metrics = spec.metrics.filter((metric): metric is TimeMetric => includes(TIME_METRICS, metric));
  const balanceNote = metrics.includes('balance') ? '; balance at the end of each period' : '';
  return {
    kind: 'time',
    // Three letters like the other charts ("Sep", not en-GB's "Sept").
    labels: groups.map((group) => (spec.granularity === 'month' ? monthName(group.first).slice(0, 3) : dayName(group.key))),
    longLabels: groups.map((group) =>
      spec.granularity === 'month' ? monthName(group.first) : spec.granularity === 'week' ? `Week of ${dayName(group.key, true)}` : dayName(group.key, true)),
    series: metrics.map((metric) => ({ metric, label: metricLabels[metric], color: metricColors[metric], values: groups.map((group) => valueOf(metric, group)) })),
    coverage: days.length
      ? `${dayName(days[0].date, true)} to ${dayName(days[days.length - 1].date, true)}, ${granularityLabels[spec.granularity]}${balanceNote}`
      : 'No bank data for the chosen months'
  };
}
