import { loadFromBackend } from '#lib/server/backend.ts';
import type { ProposalBoard, SimulatedTransaction, StoredNotification } from '#lib/forecast.ts';
import type { PageServerLoad } from './$types';

// Not awaited: the page renders at once and streams the proposals in. The first load can take a while
// because the investment agent asks the language model to draft its notification.
export const load: PageServerLoad = ({ fetch }) => ({
  board: loadFromBackend<ProposalBoard>(fetch, 'api/proposals', 150_000),
  activity: Promise.all([
    loadFromBackend<{ transactions: SimulatedTransaction[] }>(fetch, 'api/transactions'),
    loadFromBackend<{ notifications: StoredNotification[] }>(fetch, 'api/notifications?limit=20')
  ]).then(([transactions, notifications]) => ({
    transactions: transactions.ok ? transactions.data.transactions : [],
    notifications: notifications.ok ? notifications.data.notifications : []
  }))
});
