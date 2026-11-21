import { error, json } from '@sveltejs/kit';
import { backendFetch, conversationIdPattern, failOnBackendError } from '#lib/server/backend.ts';
import type { RequestHandler } from './$types';

function checkedId(id: string): string {
  if (!conversationIdPattern.test(id)) error(404, 'This conversation no longer exists.');
  return id;
}

/** Loads one conversation with its messages. */
export const GET: RequestHandler = async ({ params, fetch }) => {
  const response = await backendFetch(fetch, `api/conversations/${checkedId(params.id)}`);
  failOnBackendError(response, 'This conversation could not be loaded.');
  return json(await response.json());
};

/** Deletes one conversation. */
export const DELETE: RequestHandler = async ({ params, fetch }) => {
  const response = await backendFetch(fetch, `api/conversations/${checkedId(params.id)}`, { method: 'DELETE' });
  failOnBackendError(response, 'This conversation could not be deleted.');
  return new Response(null, { status: 204 });
};
