/** Shared helpers for the hand-built SVG charts: nice axis ticks, linear scales and axis formatters. */

/** Ticks at 1/2/5 × 10^n; the domain always contains 0 and never collapses. */
export function niceTicks(values: number[], count: number): number[] {
  const finite = values.filter(Number.isFinite);
  const low = Math.min(0, ...finite);
  const high = Math.max(0, ...finite);
  const raw = (high - low || 1) / Math.max(count, 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((factor) => factor * magnitude).find((candidate) => candidate >= raw) ?? raw;
  const start = Math.floor(low / step) * step;
  const end = high === low ? start + step * count : Math.ceil(high / step) * step;
  const steps = Math.round((end - start) / step);
  return Array.from({ length: steps + 1 }, (_, index) => Number((start + index * step).toPrecision(12)));
}

/** Maps a value from [domainStart, domainEnd] to [rangeStart, rangeEnd]. */
export const linear = (domainStart: number, domainEnd: number, rangeStart: number, rangeEnd: number) =>
  (value: number) => rangeStart + ((value - domainStart) / (domainEnd - domainStart || 1)) * (rangeEnd - rangeStart);

const compact = new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', notation: 'compact', maximumFractionDigits: 1 });
const whole = new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });

/** Axis label in euros, e.g. `€40K`, `-€10K`, `€0`. */
export const euroCompact = (euros: number) => (Number.isFinite(euros) ? compact.format(euros) : '—');

/** Whole euros for chart labels, e.g. `€7,302`. */
export const euroWhole = (euros: number) => (Number.isFinite(euros) ? whole.format(euros) : '—');

export const shortDay = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(iso));

export const weekdayDate = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(iso));
