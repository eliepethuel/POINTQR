import { createHmac } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { type Browser, type BrowserContext, type Page, expect } from '@playwright/test';
import QRCode from 'qrcode';

export interface E2EData {
  company_code: string;
  password: string;
  totp_secret: string;
  hr: string;
  staff: { admin: string; hr: string; manager: string; auditor: string };
  agents: { username: string; name: string }[];
  newcomer: { username: string; name: string };
  pairing_code: string;
  site: { id: string; latitude: number; longitude: number };
  kiosk: { id: string; key: string };
}

export function data(): E2EData {
  return JSON.parse(readFileSync(join(__dirname, '.data.json'), 'utf8')) as E2EData;
}

// --- tokens ---------------------------------------------------------------------------------

function base32(secret: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const char of secret.replace(/=+$/, '').toUpperCase()) {
    bits += alphabet.indexOf(char).toString(2).padStart(5, '0');
  }
  const bytes = bits.match(/.{8}/g) ?? [];
  return Buffer.from(bytes.map((b) => parseInt(b, 2)));
}

/** RFC 6238 code (SHA-1, 6 digits, 30 s), as given by any authenticator app. */
export function totp(secret: string, at = Date.now()): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 30_000)));
  const mac = createHmac('sha1', base32(secret)).update(counter).digest();
  const offset = mac[mac.length - 1]! & 0x0f;
  const value = (mac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return String(value).padStart(6, '0');
}

/** Kiosk QR token (ADR-0005) for a given 30 s window, signed like the tablet does. */
export function kioskToken(d: E2EData, window: number): string {
  const key = Buffer.from(d.kiosk.key, 'base64url');
  const message = `PQR1|${d.site.id}|${d.kiosk.id}|${window}`;
  const sig = createHmac('sha256', key)
    .update(message)
    .digest()
    .subarray(0, 16)
    .toString('base64url');
  return `PQR1.${d.site.id}.${d.kiosk.id}.${window}.${sig}`;
}

export const currentWindow = (): number => Math.floor(Date.now() / 30_000);

// --- fake camera ----------------------------------------------------------------------------

/**
 * Replaces the camera by a canvas stream: the test chooses the picture (a QR code) that the
 * agent app "sees". The real ZXing decoder of the app reads it.
 */
const FAKE_CAMERA = `
(() => {
  const canvas = document.createElement('canvas');
  canvas.width = 640; canvas.height = 640;
  canvas.style.cssText = 'position:fixed;left:-10000px;top:0;pointer-events:none';
  const ctx = canvas.getContext('2d');
  let image = null;
  const streams = [];
  const draw = () => {
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 640, 640);
    if (image) {
      // Natural size (scaled down only if too big): rescaling would distort the modules.
      const k = Math.min(1, 600 / Math.max(image.width, image.height));
      const w = image.width * k, h = image.height * k;
      ctx.drawImage(image, (640 - w) / 2, (640 - h) / 2, w, h);
    }
    // Manual frames: delivered even when another window has the focus.
    for (const s of streams) s.getVideoTracks()[0]?.requestFrame?.();
  };
  window.__pqShow = (src) => new Promise((resolve) => {
    const img = new Image();
    img.onload = () => { image = img; draw(); resolve(true); };
    img.src = src;
  });
  const attach = () => document.body ? document.body.append(canvas) : setTimeout(attach, 10);
  attach();
  setInterval(draw, 100);
  Object.defineProperty(navigator, 'mediaDevices', {
    value: {
      getUserMedia: () => {
        const stream = canvas.captureStream(0);
        streams.push(stream);
        draw();
        return Promise.resolve(stream);
      },
      enumerateDevices: () => Promise.resolve([]),
    },
  });
})();
`;

export interface Phone {
  context: BrowserContext;
  page: Page;
}

/** A phone: fake camera, location on (or near) the site, its own storage (device id). */
export async function phone(
  browser: Browser,
  d: E2EData,
  location?: { latitude: number; longitude: number },
): Promise<Phone> {
  const context = await browser.newContext({
    viewport: { width: 400, height: 860 },
    geolocation: { ...(location ?? d.site), accuracy: 12 },
    permissions: ['geolocation'],
  });
  await context.addInitScript(FAKE_CAMERA);
  return { context, page: await context.newPage() };
}

/** Points the phone camera at a blank wall (nothing to read). */
export async function clearCamera(page: Page): Promise<void> {
  await page.evaluate(() =>
    (window as unknown as { __pqShow(s: string): Promise<boolean> }).__pqShow(
      'data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==',
    ),
  );
}

/** Shows a QR (PNG data URL or token text) to the phone camera. */
export async function showToCamera(
  page: Page,
  qr: { token?: string; png?: Buffer },
): Promise<void> {
  const src = qr.png
    ? `data:image/png;base64,${qr.png.toString('base64')}`
    : // Same error correction level as the kiosk (L): see qr-canvas.ts.
      await QRCode.toDataURL(qr.token!, { errorCorrectionLevel: 'L', margin: 4, scale: 8 });
  await page.bringToFront();
  await page.evaluate(
    (s) => (window as unknown as { __pqShow(s: string): Promise<boolean> }).__pqShow(s),
    src,
  );
}

// --- sign-in --------------------------------------------------------------------------------

export async function signIn(page: Page, d: E2EData, username: string): Promise<void> {
  await page.goto('/connexion');
  await page.getByLabel('Code entreprise').fill(d.company_code);
  await page.getByLabel('Identifiant').fill(username);
  await page.getByLabel('Mot de passe').fill(d.password);
  await page.getByRole('button', { name: 'Se connecter' }).click();
}

/** Last 30 s window used per account: a code is accepted only once. */
const usedWindow = new Map<string, number>();

/** HR / admin sign-in, second factor included (waits for a fresh code if needed). */
export async function signInWithTotp(page: Page, d: E2EData, username: string): Promise<void> {
  await signIn(page, d, username);
  const step = page.getByRole('region', { name: 'Vérification en deux étapes' });
  await expect(step).toBeVisible();
  // Never send a code too close to the end of its window, nor the code of a previous sign-in.
  const window = Math.floor(Date.now() / 30_000);
  const left = 30 - (Math.floor(Date.now() / 1000) % 30);
  if (left < 5 || window === usedWindow.get(username)) await page.waitForTimeout(left * 1000 + 500);
  usedWindow.set(username, Math.floor(Date.now() / 30_000));
  await step.getByRole('textbox').first().click();
  await page.keyboard.type(totp(d.totp_secret));
}
