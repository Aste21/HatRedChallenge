import { derivePasswordKey, hexToBytes, sameBytes } from './crypto.ts';
import type { Statement } from '#lib/ledger.ts';
import amalfiStatement from './statements/amalfi.json';

/** What the pages may know about the signed-in business (never the password). */
export type PublicAccount = { id: string; businessName: string; ownerName: string; city: string };

type Account = PublicAccount & { username: string; passwordHash: string; statement: Statement };

/**
 * Demo accounts. To add a business: give it an id, a username and a PBKDF2 hash ("salt:hash", see
 * `hashPassword` in `crypto.ts`), a statement built by `scripts/statement.py`, and add the same id to the backend's
 * `app/accounts.py` and to the forecast service's data.
 */
const accounts: Account[] = [
  {
    id: 'amalfi',
    username: 'amalfi',
    // Demo password: "amalfi"
    passwordHash: '45a9bacc29dab8cc54fb8a413c88aa67:68ddd55a8d18b1f5a5d04bb9ded9deef941d00238bf58e3076dbf444112b65f1',
    businessName: 'Pizzeria Amalfi',
    ownerName: 'Vincenzo Amalfi',
    city: 'Frankfurt',
    statement: amalfiStatement
  }
];

const toPublic = ({ id, businessName, ownerName, city }: Account): PublicAccount => ({ id, businessName, ownerName, city });

/** Checks a username and password; returns the account, or null when either is wrong. */
export async function verifyLogin(username: string, password: string): Promise<PublicAccount | null> {
  const account = accounts.find((candidate) => candidate.username === username.trim().toLowerCase());
  // Hash even for unknown users so the response time does not reveal which usernames exist.
  const [salt, expected] = (account?.passwordHash ?? accounts[0].passwordHash).split(':');
  const matches = sameBytes(await derivePasswordKey(password, hexToBytes(salt)), hexToBytes(expected));
  return account && matches ? toPublic(account) : null;
}

export function findAccount(id: string): PublicAccount | null {
  const account = accounts.find((candidate) => candidate.id === id);
  return account ? toPublic(account) : null;
}

export function statementFor(id: string): Statement {
  const account = accounts.find((candidate) => candidate.id === id);
  if (!account) throw new Error(`Unknown account ${id}`);
  return account.statement;
}
