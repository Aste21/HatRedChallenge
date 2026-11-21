/**
 * The owner's own Overview charts, added from the chat. Kept in this browser, like the Overview layout,
 * and separate from the built-in widgets so deleting one never touches the rest.
 */
import { SPANS, type Span } from './dashboard.svelte.ts';
import { isBreakdown, normaliseSpec, specKey, type ChartSpec, type ChartType } from './charts/custom.ts';

export type CustomChart = { id: string; spec: ChartSpec; span: Span };

const MAX_CHARTS = 24;

const minSpanFor = (spec: ChartSpec): Span => (isBreakdown(spec) ? 4 : 6);

function newId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `chart-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

class CustomCharts {
  charts = $state<CustomChart[]>([]);
  visible = $derived(this.charts.map((chart) => chart.id));
  spans = $derived(Object.fromEntries(this.charts.map((chart) => [chart.id, chart.span])) as Record<string, Span>);
  #storageKey = '';

  /** Loads the account's saved charts; malformed entries are dropped. */
  restore(accountId: string) {
    this.#storageKey = `overview-custom-charts-v1:${accountId}`;
    try {
      const saved = JSON.parse(localStorage.getItem(this.#storageKey) ?? '[]');
      if (!Array.isArray(saved)) return;
      this.charts = saved.flatMap((entry) => {
        const spec = normaliseSpec(entry?.spec);
        if (!spec || typeof entry.id !== 'string') return [];
        const span = SPANS.includes(entry.span) && entry.span >= minSpanFor(spec) ? (entry.span as Span) : 12;
        return [{ id: entry.id, spec, span }];
      }).slice(0, MAX_CHARTS);
    } catch {
      // Broken saved charts are ignored.
    }
  }

  private save() {
    if (!this.#storageKey) return;
    try {
      localStorage.setItem(this.#storageKey, JSON.stringify(this.charts));
    } catch { /* private mode: the charts are not remembered */ }
  }

  get(id: string) {
    return this.charts.find((chart) => chart.id === id);
  }

  /** The saved chart that shows the same data as `spec`, if there is one. */
  find(spec: ChartSpec) {
    const key = specKey(spec);
    return this.charts.find((chart) => specKey(chart.spec) === key);
  }

  get full() {
    return this.charts.length >= MAX_CHARTS;
  }

  /** Adds a chart at the end of "Your charts"; a chart showing the same data is not added twice. */
  add(spec: ChartSpec): CustomChart | null {
    const existing = this.find(spec);
    if (existing) return existing;
    if (this.full) return null;
    const chart: CustomChart = { id: newId(), spec: $state.snapshot(spec), span: isBreakdown(spec) ? 6 : 12 };
    this.charts = [...this.charts, chart];
    this.save();
    return chart;
  }

  remove(id: string) {
    this.charts = this.charts.filter((chart) => chart.id !== id);
    this.save();
  }

  rename(id: string, title: string) {
    const cleaned = title.trim().slice(0, 80);
    if (cleaned) this.update(id, { title: cleaned });
  }

  setChartType(id: string, chartType: ChartType) {
    this.update(id, { chart_type: chartType });
  }

  private update(id: string, changes: Partial<ChartSpec>) {
    this.charts = this.charts.map((chart) => (chart.id === id ? { ...chart, spec: { ...chart.spec, ...changes } } : chart));
    this.save();
  }

  /** Moves a chart one place up (-1) or down (+1). */
  move(id: string, direction: -1 | 1) {
    const neighbour = this.visible[this.visible.indexOf(id) + direction];
    if (neighbour) this.placeBefore(id, direction < 0 ? neighbour : this.visible[this.visible.indexOf(neighbour) + 1] ?? null);
  }

  /** Puts `id` right before `beforeId` (or at the end when `beforeId` is null). */
  placeBefore(id: string, beforeId: string | null) {
    if (id === beforeId) return;
    const moving = this.get(id);
    if (!moving) return;
    const rest = this.charts.filter((chart) => chart.id !== id);
    const at = beforeId === null ? rest.length : rest.findIndex((chart) => chart.id === beforeId);
    rest.splice(at < 0 ? rest.length : at, 0, moving);
    if (rest.map((chart) => chart.id).join() !== this.visible.join()) { this.charts = rest; this.save(); }
  }

  /** Allowed widths for a chart, narrowest first. */
  spansFor(id: string): Span[] {
    const chart = this.get(id);
    const minSpan = chart ? minSpanFor(chart.spec) : 4;
    return SPANS.filter((span) => span >= minSpan);
  }

  /** Sets a chart's width, snapped to the nearest allowed width. */
  resize(id: string, columns: number) {
    const span = this.spansFor(id).reduce((best, candidate) => (Math.abs(candidate - columns) < Math.abs(best - columns) ? candidate : best));
    if (this.spans[id] !== span) {
      this.charts = this.charts.map((chart) => (chart.id === id ? { ...chart, span } : chart));
      this.save();
    }
  }
}

export const customCharts = new CustomCharts();
