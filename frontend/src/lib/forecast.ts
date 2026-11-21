/** Shapes returned by the backend's /api/forecast and /api/proposals (amounts in EUR, not cents). */

export type ForecastDay = { date: string; p5: number; p50: number; p95: number };

export type SafeToLock = { days: number; amount: number; lowest_balance: number };

export type Forecast = {
  as_of: string;
  start_balance: number;
  official: {
    buffer: { amount: number; source: string };
    safe_to_lock: SafeToLock[];
    p_below_zero: number;
    end_balance_p50: number;
    daily: ForecastDay[];
  };
};

export type ProposalStatus = 'awaiting_approval' | 'approved' | 'declined' | 'superseded';

export type Proposal = {
  id: string;
  kind: 'fixed_term_deposit' | 'credit_line';
  title: string;
  amount: number;
  term_days: number | null;
  annual_rate_pct: number | null;
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

/** Formats euros (not cents) the same way as the rest of the UI. */
export const euro = (amount: number) =>
  new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(amount);
