import { loadFromBackend } from '#lib/server/backend.ts';
import type { Forecast } from '#lib/forecast.ts';
import type { PageServerLoad } from './$types';

// Not awaited: the page renders at once from the statement fixture and the forecast streams in,
// so switching tabs never waits for the forecast service.
export const load: PageServerLoad = ({ fetch }) => ({
  forecast: loadFromBackend<Forecast>(fetch, 'api/forecast?horizon=90').then((loaded) => (loaded.ok ? loaded.data : null))
});
