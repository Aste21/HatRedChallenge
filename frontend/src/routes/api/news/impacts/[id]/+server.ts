import { error } from '@sveltejs/kit';
import { articleIdPattern, backendFetch } from '#lib/server/backend.ts';
import type { RequestHandler } from './$types';

/** Removes an article's events from the forecast. */
export const DELETE: RequestHandler = async ({ params, fetch }) => {
  if (!articleIdPattern.test(params.id)) error(400, 'Unknown article.');
  const response = await backendFetch(fetch, `api/news/impacts/${params.id}`, { method: 'DELETE' });
  if (!response.ok && response.status !== 404) error(502, 'The article could not be removed right now.');
  return new Response(null, { status: 204 });
};
