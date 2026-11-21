/** Small helpers around the Web Crypto API (available in Node and every modern runtime). */

export const bytesToHex = (bytes: Uint8Array) => Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');

export const hexToBytes = (hex: string) => Uint8Array.from(hex.match(/../g) ?? [], (pair) => parseInt(pair, 16));

/** Compares in constant time for equal lengths, so a comparison does not leak how many bytes matched. */
export function sameBytes(first: Uint8Array, second: Uint8Array): boolean {
  if (first.length !== second.length) return false;
  let difference = 0;
  for (let index = 0; index < first.length; index++) difference |= first[index] ^ second[index];
  return difference === 0;
}

const PASSWORD_ITERATIONS = 210_000;

/** PBKDF2-SHA-256 of a password with the given salt, as 32 bytes. */
export async function derivePasswordKey(password: string, salt: Uint8Array): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', hash: 'SHA-256', salt: salt as BufferSource, iterations: PASSWORD_ITERATIONS }, key, 256
  );
  return new Uint8Array(bits);
}

/** Hash for the account list, as "salt:hash" in hex. */
export async function hashPassword(password: string): Promise<string> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return `${bytesToHex(salt)}:${bytesToHex(await derivePasswordKey(password, salt))}`;
}
