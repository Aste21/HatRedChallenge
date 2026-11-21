import { loadFromBackend } from '#lib/server/backend.ts';
import type { ProposalBoard } from '#lib/forecast.ts';
import type { PageServerLoad } from './$types';

// Not awaited: the page renders at once and streams the proposals in. The first load can take a while
// because the investment agent asks the language model to draft its notification.
export const load: PageServerLoad = ({ fetch }) => ({
  board: loadFromBackend<ProposalBoard>(fetch, 'api/proposals', 150_000)
});
