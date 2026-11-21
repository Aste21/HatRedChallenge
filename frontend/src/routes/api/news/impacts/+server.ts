import { error, json } from '@sveltejs/kit';
import { articleIdPattern, backendFetch } from '#lib/server/backend.ts';
import type { RequestHandler } from './$types';

/** Asks the backend how an article changes the forecast; the resulting events are applied to it. */
export const POST: RequestHandler = async ({ request, fetch }) => {
  const payload = await request.json().catch(() => null);
  const articleId = payload?.article_id;
  const title = typeof payload?.title === 'string' ? payload.title.trim().slice(0, 500) : '';
  const summary = typeof payload?.summary === 'string' ? payload.summary.slice(0, 4000) : '';
  if (typeof articleId !== 'string' || !articleIdPattern.test(articleId) || !title) error(400, 'Unknown article.');

  const response = await backendFetch(fetch, 'api/news/impacts', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ article_id: articleId, title, summary }),
    timeoutMs: 150_000
  });
  if (!response.ok) error(502, 'The forecast could not check this article right now. Please try again.');
  return json(await response.json());
};
