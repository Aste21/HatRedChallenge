import { error, json } from '@sveltejs/kit';
import { backendFetch, failOnBackendError } from '#lib/server/backend.ts';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ fetch }) => {
  const response = await backendFetch(fetch, 'api/dashboard-defaults');
  failOnBackendError(response, 'The default charts could not be loaded.');
  return json(await response.json());
};

const write: RequestHandler = async ({ fetch, request }) => {
  if (!request.headers.get('content-type')?.startsWith('application/json')) {
    error(415, 'Expected a JSON chart layout.');
  }
  const response = await backendFetch(fetch, 'api/dashboard-defaults', {
    method: request.method,
    headers: { 'Content-Type': 'application/json' },
    body: await request.text()
  });
  failOnBackendError(response, 'The default charts could not be saved.');
  return new Response(null, { status: 204 });
};

export const PUT = write;
export const POST = write;
