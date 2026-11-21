import { error, json } from '@sveltejs/kit';
import { backendFetch } from '#lib/server/backend.ts';
import type { RequestHandler } from './$types';

const proposalIdPattern = /^[a-z0-9_-]{1,80}$/;

/** Forwards the owner's approve/decline decision to the backend, which records a simulated transaction. */
export const POST: RequestHandler = async ({ params, request, fetch }) => {
  if (!proposalIdPattern.test(params.id)) error(400, 'Unknown proposal.');
  const payload = await request.json().catch(() => null);
  const decision = payload?.decision;
  if (decision !== 'approved' && decision !== 'declined') error(400, 'Please approve or decline.');

  const response = await backendFetch(fetch, `api/proposals/${params.id}/decision`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ decision }),
    timeoutMs: 150_000
  });
  if (response.status === 404) error(404, 'This proposal is no longer available. Refresh the page.');
  if (response.status === 409) error(409, 'This proposal was already decided, or another option was chosen.');
  if (!response.ok) error(502, 'The decision could not be saved right now. Please try again.');
  const result = await response.json();
  return json({ status: result.proposal?.status, notification_status: result.notification_status ?? null });
};
