import { error } from '@sveltejs/kit';
import { CHAT_API_URL } from '$app/env/private';

export const conversationIdPattern = /^[a-f0-9]{32}$/;

/** Calls the Python backend; the browser never talks to it directly. Network failures become HTTP 502. */
export async function backendFetch(
  fetch: typeof globalThis.fetch,
  path: string,
  { timeoutMs = 10_000, ...init }: RequestInit & { timeoutMs?: number } = {}
): Promise<Response> {
  try {
    return await fetch(new URL(path, CHAT_API_URL.replace(/\/?$/, '/')), {
      ...init,
      signal: AbortSignal.timeout(timeoutMs)
    });
  } catch {
    error(502, 'The assistant is not reachable right now.');
  }
}

export type Loaded<T> = { ok: true; data: T } | { ok: false; message: string };

/** Loads JSON for a page; a failing backend becomes a message instead of an error page. */
export async function loadFromBackend<T>(
  fetch: typeof globalThis.fetch,
  path: string,
  timeoutMs = 10_000
): Promise<Loaded<T>> {
  try {
    const response = await fetch(new URL(path, CHAT_API_URL.replace(/\/?$/, '/')), {
      signal: AbortSignal.timeout(timeoutMs)
    });
    if (response.ok) return { ok: true, data: (await response.json()) as T };
    const detail = await response.json().then((body) => body?.detail).catch(() => null);
    return { ok: false, message: typeof detail === 'string' ? detail : 'The service is not available right now.' };
  } catch {
    return { ok: false, message: 'The service is not reachable right now.' };
  }
}

/** Maps backend errors to messages a non-technical owner understands. */
export function failOnBackendError(response: Response, fallback: string): void {
  if (response.status === 404) error(404, 'This conversation no longer exists.');
  if (!response.ok) error(502, fallback);
}
