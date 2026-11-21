import { NEWS_API_URL } from '$app/env/private';
import { loadFromBackend } from '#lib/server/backend.ts';
import type { Article, NewsImpact } from '#lib/forecast.ts';
import type { PageServerLoad } from './$types';

async function loadArticles(fetch: typeof globalThis.fetch) {
  if (!NEWS_API_URL) return { feed: 'unconfigured', articles: [] as Article[] };
  try {
    const url = new URL('articles', NEWS_API_URL.replace(/\/?$/, '/'));
    url.searchParams.set('status', 'accepted');
    const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error('News service unavailable');
    const payload = await response.json();
    if (!Array.isArray(payload.articles)) throw new Error('Invalid article list');
    const articles: Article[] = payload.articles.filter((item: Article) =>
      item && typeof item.title === 'string' && typeof item.url === 'string' && /^https:\/\//i.test(item.url));
    return { feed: 'connected', articles };
  } catch { return { feed: 'unavailable', articles: [] as Article[] }; }
}

export const load: PageServerLoad = async ({ fetch }) => {
  const [news, impacts] = await Promise.all([
    loadArticles(fetch),
    loadFromBackend<{ impacts: NewsImpact[] }>(fetch, 'api/news/impacts', 5000)
  ]);
  return { ...news, impacts: impacts.ok ? impacts.data.impacts : [] };
};
