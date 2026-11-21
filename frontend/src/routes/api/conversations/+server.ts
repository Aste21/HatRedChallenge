import { json } from '@sveltejs/kit';
import { backendFetch, failOnBackendError } from '#lib/server/backend.ts';
import type { RequestHandler } from './$types';

/** Lists stored conversations, most recent first. */
export const GET: RequestHandler = async ({ fetch }) => {
  const response = await backendFetch(fetch, 'api/conversations?limit=50');
  failOnBackendError(response, 'The chat history could not be loaded.');
  return json(await response.json());
};
