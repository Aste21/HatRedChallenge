import { SESSION_SECRET } from '$app/env/private';
import { bytesToHex, sameBytes } from './crypto.ts';

export const SESSION_COOKIE = 'session';
export const SESSION_DAYS = 7;

// Without SESSION_SECRET every server start gets a new key, which simply signs everyone out.
const secret = SESSION_SECRET ?? bytesToHex(crypto.getRandomValues(new Uint8Array(32)));
if (!SESSION_SECRET) console.warn('SESSION_SECRET is not set: sessions end when the server restarts.');

const signingKey = crypto.subtle.importKey(
  'raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
);

async function sign(payload: string): Promise<string> {
  const signature = await crypto.subtle.sign('HMAC', await signingKey, new TextEncoder().encode(payload));
  return bytesToHex(new Uint8Array(signature));
}

/** A signed, expiring session token: `<account id>.<expiry ms>.<signature>`. */
export async function createSessionToken(accountId: string): Promise<string> {
  const payload = `${accountId}.${Date.now() + SESSION_DAYS * 86_400_000}`;
  return `${payload}.${await sign(payload)}`;
}

/** Returns the account id of a valid, unexpired token, otherwise null. */
export async function readSessionToken(token: string | undefined): Promise<string | null> {
  const parts = token?.split('.') ?? [];
  if (parts.length !== 3) return null;
  const [accountId, expires, signature] = parts;
  const expected = await sign(`${accountId}.${expires}`);
  if (!sameBytes(new TextEncoder().encode(expected), new TextEncoder().encode(signature))) return null;
  return Number(expires) > Date.now() ? accountId : null;
}
