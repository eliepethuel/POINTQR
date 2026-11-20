import {
  base64UrlDecode,
  base64UrlEncode,
  importHmacKey,
  kioskToken,
  personalToken,
  tokenKind,
  windowOf,
} from './qr-token';

/** Same vectors as backend/apps/attendance/tests/test_tokens.py: tablet and server must agree. */
const KEY = 'AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8'; // bytes 0..31
const VECTOR_KIOSK =
  'PQR1.11111111-1111-4111-8111-111111111111.22222222-2222-4222-8222-222222222222.59866666.MkC1r8KnJjqr91esqEC3ZA';
const VECTOR_PERSONAL = 'PQRP.33333333-3333-4333-8333-333333333333.59866666.vkZfWjvmwM4TD5h3UfUw7w';

describe('qr-token', () => {
  it('produces the server kiosk token byte for byte', async () => {
    const key = await importHmacKey(KEY);
    const token = await kioskToken(
      key,
      '11111111-1111-4111-8111-111111111111',
      '22222222-2222-4222-8222-222222222222',
      59866666,
    );
    expect(token).toBe(VECTOR_KIOSK);
  });

  it('produces the server personal token byte for byte', async () => {
    const key = await importHmacKey(KEY);
    expect(await personalToken(key, '33333333-3333-4333-8333-333333333333', 59866666)).toBe(
      VECTOR_PERSONAL,
    );
  });

  it('keeps the key non-extractable', async () => {
    const key = await importHmacKey(KEY);
    expect(key.extractable).toBe(false);
  });

  it('uses 30-second windows', () => {
    const t0 = Date.UTC(2026, 10, 20, 7, 0, 0);
    expect(windowOf(t0 + 29_000)).toBe(windowOf(t0));
    expect(windowOf(t0 + 30_000)).toBe(windowOf(t0) + 1);
  });

  it('round-trips base64url', () => {
    const bytes = base64UrlDecode(KEY);
    expect(bytes.length).toBe(32);
    expect(base64UrlEncode(bytes)).toBe(KEY);
  });

  it('recognises token kinds', () => {
    expect(tokenKind(VECTOR_KIOSK)).toBe('PQR1');
    expect(tokenKind('PQRB.x.1.sig')).toBe('PQRB');
    expect(tokenKind('https://example.com')).toBeNull();
  });
});
