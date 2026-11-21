import { statementFor } from '#lib/server/accounts.ts';
import type { LayoutServerLoad } from './$types';

// hooks.server.ts already sent signed-out visitors to /login, so an account is always present here.
export const load: LayoutServerLoad = ({ locals }) => ({
  account: locals.account!,
  statement: statementFor(locals.account!.id)
});
