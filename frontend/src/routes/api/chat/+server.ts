import { error, json } from '@sveltejs/kit';
import { backendFetch, conversationIdPattern, failOnBackendError } from '#lib/server/backend.ts';
import type { RequestHandler } from './$types';

type PageContext = { path: string; title: string; content: string };

const isPageContext = (value: unknown): value is PageContext =>
  typeof value === 'object' && value !== null &&
  ['path', 'title', 'content'].every((key) => typeof (value as Record<string, unknown>)[key] === 'string');

/** Forwards a new message (plus what the owner sees on the current page) to the backend chat agent. */
export const POST: RequestHandler = async ({ request, fetch }) => {
  const payload = await request.json().catch(() => null);
  const message = typeof payload?.message === 'string' ? payload.message.trim() : '';
  const conversationId = payload?.conversation_id ?? null;
  const pageContext = payload?.page_context ?? null;
  if (!message || message.length > 4000) error(400, 'Please type a question (up to 4000 characters).');
  if (conversationId !== null && !(typeof conversationId === 'string' && conversationIdPattern.test(conversationId))) {
    error(400, 'Unknown conversation.');
  }
  if (pageContext !== null && !isPageContext(pageContext)) error(400, 'Invalid page content.');

  const response = await backendFetch(fetch, 'api/chat', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
      page_context: pageContext && {
        path: pageContext.path.slice(0, 200),
        title: pageContext.title.slice(0, 200),
        content: pageContext.content.slice(0, 8000)
      }
    }),
    timeoutMs: 90_000
  });
  if (response.status === 422) error(422, 'The safety check blocked the message or its context. Remove sensitive details and try again.');
  if (response.status === 503) error(503, 'The safety check is unavailable. Please try again shortly.');
  failOnBackendError(response, 'The assistant could not answer right now.');
  const answer = await response.json();
  return json({
    conversation_id: String(answer.conversation_id),
    title: String(answer.title ?? ''),
    reply: typeof answer.reply === 'string' ? answer.reply : ''
  });
};
