import { type Page, expect, test } from '@playwright/test';

import {
  type E2EData,
  type Phone,
  clearCamera,
  currentWindow,
  data,
  kioskToken,
  phone,
  showToCamera,
  signIn,
  signInWithTotp,
} from './support';

/**
 * The acceptance journeys of the specification, through the real stack: a tablet paired from
 * the back-office code, phones that scan it, HR that validates a correction.
 */
test.describe.serial('Pointage de bout en bout', () => {
  let d: E2EData;
  let kiosk: Page;
  let agentA: Phone;
  let agentB: Phone;

  test.beforeAll(() => {
    d = data();
  });

  test.afterAll(async () => {
    await Promise.all([agentA?.context.close(), agentB?.context.close(), kiosk?.context().close()]);
  });

  async function activate(p: Page, username: string): Promise<void> {
    await signIn(p, d, username);
    await expect(p).toHaveURL(/\/agent/);
    await p.getByRole('button', { name: 'Activer ce téléphone' }).click();
    await expect(p.getByRole('button', { name: 'Pointer' })).toBeVisible();
  }

  async function result(p: Page): Promise<string> {
    const dialog = p.getByRole('alertdialog');
    await expect(dialog).toBeVisible({ timeout: 20_000 });
    const text = await dialog.innerText();
    await clearCamera(p); // the agent lowers the phone
    await dialog.getByRole('button', { name: 'Terminé' }).click();
    return text;
  }

  test('une tablette s’appaire avec le code du back-office et affiche le QR', async ({
    browser,
  }) => {
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    kiosk = await context.newPage();
    await kiosk.goto('/kiosk');
    await kiosk.getByLabel('Code entreprise').fill(d.company_code);
    await kiosk.getByRole('textbox').nth(1).click();
    await kiosk.keyboard.type(d.pairing_code);
    await expect(
      kiosk
        .getByText('Scannez ce code avec l’application PointQR')
        .or(kiosk.getByText("Scannez ce code avec l'application PointQR")),
    ).toBeVisible();
    await expect(kiosk.getByRole('img', { name: /QR code de pointage/ })).toBeVisible();
  });

  test('R1 — l’agent active son téléphone et scanne la borne : pointage accepté', async ({
    browser,
  }) => {
    agentA = await phone(browser, d);
    await activate(agentA.page, d.agents[0]!.username);
    // The phone camera sees exactly what the kiosk draws: its canvas, read pixel for pixel
    // (a page screenshot can catch the element while it moves). New frames keep coming, like
    // a phone filming the tablet across a 30 s QR change.
    const qr = kiosk.getByRole('img', { name: /QR code de pointage/ });
    const dialog = agentA.page.getByRole('alertdialog');
    for (let i = 0; i < 10 && !(await dialog.isVisible()); i++) {
      const dataUrl = await qr.evaluate((c: HTMLCanvasElement) => c.toDataURL('image/png'));
      await showToCamera(agentA.page, { png: Buffer.from(dataUrl.split(',')[1]!, 'base64') });
      await dialog.waitFor({ timeout: 2_000 }).catch(() => undefined);
    }
    const text = await result(agentA.page);
    expect(text).toContain('Entrée enregistrée');
    expect(text).toMatch(/À l’heure|À l'heure|Retard de \d+ min|enregistré/);
    await agentA.page.getByRole('button', { name: "Aujourd'hui" }).click();
    await expect(agentA.page.getByText('Entrée').first()).toBeVisible();
  });

  test('R2 — une photo du QR prise il y a 2 minutes est refusée (QR expiré)', async ({
    browser,
  }) => {
    agentB = await phone(browser, d);
    await activate(agentB.page, d.agents[1]!.username);
    await showToCamera(agentB.page, { token: kioskToken(d, currentWindow() - 4) });
    const text = await result(agentB.page);
    expect(text).toContain('Pointage refusé');
    expect(text).toContain('QR expiré');
  });

  test('un pointage depuis la maison est refusé (hors zone)', async () => {
    await agentB.context.setGeolocation({ latitude: 5.36, longitude: -3.95, accuracy: 10 });
    await showToCamera(agentB.page, { token: kioskToken(d, currentWindow()) });
    const text = await result(agentB.page);
    expect(text).toContain('Pointage refusé');
    expect(text).toContain('Hors zone');
  });

  test('R3 — le téléphone de B ne peut pas servir à l’agent C', async () => {
    const p = agentB.page;
    await p.getByRole('button', { name: 'Se déconnecter' }).click();
    await expect(p).toHaveURL(/\/connexion/); // let the logout request finish
    await signIn(p, d, d.agents[2]!.username);
    await expect(p).toHaveURL(/\/agent/);
    await p.getByRole('button', { name: 'Activer ce téléphone' }).click();
    await expect(p.getByRole('alert')).toContainText('déjà lié à un autre agent');
  });

  test('R7 — arrivée oubliée hier : l’agent la demande, le RH la valide', async ({ browser }) => {
    const p = agentA.page;
    const reason = `Badgeuse indisponible à l'arrivée (essai ${Date.now()})`;
    // A correction is always about the past: yesterday's arrival (Abidjan time = UTC).
    const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);
    await p.getByRole('link', { name: 'Mes demandes' }).click();
    await p.getByRole('button', { name: 'Nouvelle demande' }).click();
    await p.getByLabel('Objet').selectOption({ label: 'Oubli de pointage' });
    await p.getByLabel('Date concernée').fill(yesterday);
    await p.getByLabel('Sens').selectOption('in');
    await p.getByLabel('Heure réelle').fill('07:25');
    await p.getByLabel('Motif').fill(reason);
    await p.getByRole('button', { name: 'Envoyer' }).click();
    await expect(p.getByText(reason)).toBeVisible();

    const hrContext = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const hr = await hrContext.newPage();
    await signInWithTotp(hr, d, d.hr);
    await expect(hr).toHaveURL(/tableau-de-bord/);
    await hr.getByRole('link', { name: 'Demandes' }).click();
    const card = hr.locator('article', { hasText: reason });
    await expect(card).toBeVisible();
    await card.getByRole('button', { name: 'Valider' }).click();
    await hr.getByRole('button', { name: 'Toutes' }).click();
    await expect(card).toContainText('Validée');

    // The original check-in is kept: the corrected exit is added next to it.
    await hr.getByRole('link', { name: 'Pointages' }).click();
    await hr.getByLabel('Jour').fill(yesterday);
    const rows = hr.getByRole('row').filter({ hasText: d.agents[0]!.name });
    await expect(rows.filter({ hasText: 'correction' })).toHaveCount(1);
    await expect(rows.filter({ hasText: 'correction' })).toContainText('07:25');
    await hrContext.close();
  });
});
