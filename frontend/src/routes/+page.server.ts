import { loadFromBackend } from '#lib/server/backend.ts';
import type { Forecast } from '#lib/forecast.ts';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
  const forecast = await loadFromBackend<Forecast>(fetch, 'api/forecast?horizon=90');
  return { forecast: forecast.ok ? forecast.data : null };
};
