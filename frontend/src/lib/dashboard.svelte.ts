/** The owner's Overview layout: which widgets are shown, in which order and how wide, kept in this browser. */

/** Widths in columns of the 12-column grid: a third, a half, two thirds, full width. */
export const SPANS = [4, 6, 8, 12] as const;
export type Span = (typeof SPANS)[number];
export const spanLabels: Record<Span, string> = { 4: '⅓', 6: '½', 8: '⅔', 12: 'Full' };
export const spanNames: Record<Span, string> = { 4: 'one third', 6: 'half', 8: 'two thirds', 12: 'full width' };

export type Widget = { id: string; title: string; span: Span; minSpan: Span };

// Default widths add up to 12 per row, so the default layout has no gaps.
export const widgets: Widget[] = [
  { id: 'summary', title: 'Balance summary', span: 12, minSpan: 4 },
  { id: 'outlook', title: 'Next 90 days', span: 12, minSpan: 6 },
  { id: 'forecast', title: 'Forecast', span: 8, minSpan: 6 },
  { id: 'payments', title: 'Upcoming payments', span: 4, minSpan: 4 },
  { id: 'liquidity', title: 'Liquidity', span: 8, minSpan: 6 },
  { id: 'weekday', title: 'Average takings by weekday', span: 4, minSpan: 4 },
  { id: 'news', title: 'News in your forecast', span: 6, minSpan: 4 },
  { id: 'spending', title: 'Where the money goes', span: 6, minSpan: 4 },
  { id: 'monthly', title: 'Money in and out per month', span: 12, minSpan: 6 },
  { id: 'calendar', title: 'Your year at a glance', span: 12, minSpan: 8 }
];

const byId = new Map(widgets.map((widget) => [widget.id, widget]));
const defaultOrder = widgets.map((widget) => widget.id);
const defaultSpans = () => Object.fromEntries(widgets.map((widget) => [widget.id, widget.span])) as Record<string, Span>;

class DashboardLayout {
  order = $state<string[]>([...defaultOrder]);
  hidden = $state<string[]>([]);
  spans = $state<Record<string, Span>>(defaultSpans());
  visible = $derived(this.order.filter((id) => !this.hidden.includes(id)));
  #storageKey = '';

  /** Restores the account's saved layout; unknown ids are dropped, new widgets appended, bad widths reset. */
  restore(accountId: string) {
    this.#storageKey = `overview-layout-v2:${accountId}`;
    try {
      const saved = JSON.parse(localStorage.getItem(this.#storageKey) ?? 'null');
      if (!saved || !Array.isArray(saved.order) || !Array.isArray(saved.hidden)) return;
      const known = saved.order.filter((id: unknown): id is string => typeof id === 'string' && byId.has(id));
      this.order = [...known, ...defaultOrder.filter((id) => !known.includes(id))];
      this.hidden = saved.hidden.filter((id: unknown): id is string => typeof id === 'string' && byId.has(id));
      const spans = defaultSpans();
      for (const [id, span] of Object.entries(saved.spans ?? {})) {
        const widget = byId.get(id);
        if (widget && SPANS.includes(span as Span) && (span as Span) >= widget.minSpan) spans[id] = span as Span;
      }
      this.spans = spans;
    } catch {
      // A broken saved layout falls back to the default one.
    }
  }

  private save() {
    if (!this.#storageKey) return;
    try {
      localStorage.setItem(this.#storageKey, JSON.stringify({ order: this.order, hidden: this.hidden, spans: this.spans }));
    } catch { /* private mode: the layout is not remembered */ }
  }

  /** Moves a widget one place up (-1) or down (+1) among the visible widgets. */
  move(id: string, direction: -1 | 1) {
    const visible = this.visible;
    const neighbour = visible[visible.indexOf(id) + direction];
    if (neighbour) this.placeBefore(id, direction < 0 ? neighbour : visible[visible.indexOf(neighbour) + 1] ?? null);
  }

  /** Puts `id` right before `beforeId` (or at the end when `beforeId` is null). */
  placeBefore(id: string, beforeId: string | null) {
    if (id === beforeId) return;
    const rest = this.order.filter((item) => item !== id);
    const at = beforeId === null ? rest.length : rest.indexOf(beforeId);
    rest.splice(at < 0 ? rest.length : at, 0, id);
    if (rest.join() !== this.order.join()) { this.order = rest; this.save(); }
  }

  /** Allowed widths for a widget, narrowest first. */
  spansFor(id: string): Span[] {
    const minSpan = byId.get(id)?.minSpan ?? 4;
    return SPANS.filter((span) => span >= minSpan);
  }

  /** Sets a widget's width, snapped to the nearest allowed width. */
  resize(id: string, columns: number) {
    const allowed = this.spansFor(id);
    const span = allowed.reduce((best, candidate) => (Math.abs(candidate - columns) < Math.abs(best - columns) ? candidate : best));
    if (this.spans[id] !== span) { this.spans = { ...this.spans, [id]: span }; this.save(); }
  }

  toggle(id: string) {
    this.hidden = this.hidden.includes(id) ? this.hidden.filter((item) => item !== id) : [...this.hidden, id];
    this.save();
  }

  reset() {
    this.order = [...defaultOrder];
    this.hidden = [];
    this.spans = defaultSpans();
    this.save();
  }
}

export const layout = new DashboardLayout();
