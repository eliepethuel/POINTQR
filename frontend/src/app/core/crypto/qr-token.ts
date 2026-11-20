/**
 * QR tokens computed in the browser with WebCrypto — byte-for-byte identical to
 * backend/apps/attendance/tokens.py (ADR-0005). The key is imported as non-extractable.
 */
export const WINDOW_SECONDS = 30;
const SIGNATURE_BYTES = 16;

export function windowOf(epochMs: number): number {
  return Math.floor(epochMs / 1000 / WINDOW_SECONDS);
}

export function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function base64UrlDecode(text: string): Uint8Array<ArrayBuffer> {
  const padded =
    text.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (text.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/** Imports a raw base64url HMAC-SHA256 key that JavaScript can use but never read back. */
export function importHmacKey(secretB64Url: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'raw',
    base64UrlDecode(secretB64Url),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
}

async function signature(key: CryptoKey, message: string): Promise<string> {
  const mac = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(message));
  return base64UrlEncode(new Uint8Array(mac).slice(0, SIGNATURE_BYTES));
}

/** Dynamic kiosk QR (mode A): PQR1.<site>.<kiosk>.<window>.<sig>. */
export async function kioskToken(
  key: CryptoKey,
  site: string,
  kiosk: string,
  window: number,
): Promise<string> {
  return `PQR1.${site}.${kiosk}.${window}.${await signature(key, `PQR1|${site}|${kiosk}|${window}`)}`;
}

/** Rotating personal QR shown by the agent app (mode B): PQRP.<agent>.<window>.<sig>. */
export async function personalToken(
  key: CryptoKey,
  agent: string,
  window: number,
): Promise<string> {
  return `PQRP.${agent}.${window}.${await signature(key, `PQRP|${agent}|${window}`)}`;
}

/** Which kind of QR a scanned text is (the scanner ignores anything else). */
export function tokenKind(text: string): 'PQR1' | 'PQRP' | 'PQRB' | 'PQRS' | null {
  const prefix = text.split('.', 1)[0];
  return prefix === 'PQR1' || prefix === 'PQRP' || prefix === 'PQRB' || prefix === 'PQRS'
    ? prefix
    : null;
}
