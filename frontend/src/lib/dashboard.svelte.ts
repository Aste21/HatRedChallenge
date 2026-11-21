/** The owner's Overview layout: which widgets are shown and in which order, kept in this browser. */

export type WidgetSize = 'full' | 'wide' | 'narrow' | 'half';
export type Widget = { id: string; title: string; size: WidgetSize };

export const widgets: Widget[] = [
  { id: 'summary', title: 'Balance summary', size: 'full' },
  { id: 'outlook', title: 'Next 90 days', size: 'full' },
  { id: 'balance', title: 'Balance over time', size: 'wide' },
  { id: 'payments', title: 'Upcoming payments', size: 'narrow' },
  { id: 'news', title: 'News in your forecast', size: 'full' },
  { id: 'monthly', title: 'Money in and out per month', size: 'full' },
  { id: 'spending', title: 'Where the money goes', size: 'half' },
  { id: 'weekday', title: 'Average takings by weekday', size: 'half' },
  { id: 'calendar', title: 'Your year at a glance', size: 'full' }
];

const STORAGE_KEY = 'overview-layout-v1';
const defaultOrder = widgets.map((widget) => widget.id);

class DashboardLayout {
  order = $state<string[]>([...defaultOrder]);
  hidden = $state<string[]>([]);
  visible = $derived(this.order.filter((id) => !this.hidden.includes(id)));

  /** Restores the saved layout; unknown ids are dropped and new widgets are appended. */
  restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null');
      if (!saved || !Array.isArray(saved.order) || !Array.isArray(saved.hidden)) return;
      const known = saved.order.filter((id: unknown): id is string => typeof id === 'string' && defaultOrder.includes(id));
      this.order = [...known, ...defaultOrder.filter((id) => !known.includes(id))];
      this.hidden = saved.hidden.filter((id: unknown): id is string => typeof id === 'string' && defaultOrder.includes(id));
    } catch {
      // A broken saved layout falls back to the default one.
    }
  }

  private save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ order: this.order, hidden: this.hidden })); } catch { /* private mode */ }
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

  toggle(id: string) {
    this.hidden = this.hidden.includes(id) ? this.hidden.filter((item) => item !== id) : [...this.hidden, id];
    this.save();
  }

  reset() {
    this.order = [...defaultOrder];
    this.hidden = [];
    this.save();
  }
}

export const layout = new DashboardLayout();
