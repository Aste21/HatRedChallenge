import { json, redirect } from '@sveltejs/kit';
import type { Handle, HandleFetch } from '@sveltejs/kit/hooks';
import { CHAT_API_URL } from '$app/env/private';
import { findAccount } from '#lib/server/accounts.ts';
import { readSessionToken, SESSION_COOKIE } from '#lib/server/session.ts';

const protectedPrefixes = ['/overview', '/proposals', '/news', '/assistant', '/api'];
const backendBase = CHAT_API_URL.replace(/\/?$/, '/');

/** Reads the session cookie and keeps signed-out visitors away from the app and its API. */
export const handle: Handle = async ({ event, resolve }) => {
  const accountId = await readSessionToken(event.cookies.get(SESSION_COOKIE));
  event.locals.account = accountId ? findAccount(accountId) : null;

  const path = event.url.pathname;
  const isProtected = protectedPrefixes.some((prefix) => path === prefix || path.startsWith(prefix + '/'));
  if (isProtected && !event.locals.account) {
    if (path.startsWith('/api')) return json({ message: 'Please log in again.' }, { status: 401 });
    redirect(303, `/login?next=${encodeURIComponent(path + event.url.search)}`);
  }
  return resolve(event);
};

/** Tells the backend which business is signed in; the browser never calls the backend itself. */
export const handleFetch: HandleFetch = async ({ event, request, fetch }) => {
  if (request.url.startsWith(backendBase)) {
    request.headers.delete('x-account-id');
    if (event.locals.account) request.headers.set('x-account-id', event.locals.account.id);
  }
  return fetch(request);
};
