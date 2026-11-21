import { fail, redirect } from '@sveltejs/kit';
import { verifyLogin } from '#lib/server/accounts.ts';
import { createSessionToken, SESSION_COOKIE, SESSION_DAYS } from '#lib/server/session.ts';
import type { Actions, PageServerLoad } from './$types';

/** Only same-site paths, so the login cannot be used to send people to another website. */
function safeNext(next: string | null): string {
  return next && /^\/(?![/\\])/.test(next) ? next : '/overview';
}

export const load: PageServerLoad = ({ locals, url }) => {
  if (locals.account) redirect(303, safeNext(url.searchParams.get('next')));
};

export const actions: Actions = {
  default: async ({ request, cookies, url }) => {
    const form = await request.formData();
    const username = String(form.get('username') ?? '');
    const password = String(form.get('password') ?? '');
    if (!username.trim() || !password) return fail(400, { username, missing: true });

    const account = await verifyLogin(username, password);
    if (!account) return fail(400, { username, incorrect: true });

    cookies.set(SESSION_COOKIE, await createSessionToken(account.id), {
      path: '/', httpOnly: true, sameSite: 'lax', secure: url.protocol === 'https:', maxAge: SESSION_DAYS * 86_400
    });
    redirect(303, safeNext(url.searchParams.get('next')));
  }
};
