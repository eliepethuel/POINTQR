import { expect, test } from '@playwright/test';

import { data, phone, signInWithTotp } from './support';

/** EF-09: HR invites a new agent, who activates their access from the link on their phone. */
test('le RH invite un agent, qui active son accès puis arrive sur l’application', async ({
  browser,
}) => {
  test.setTimeout(120_000);
  const d = data();
  const hrContext = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const hr = await hrContext.newPage();
  await signInWithTotp(hr, d, d.hr);
  await expect(hr).toHaveURL(/tableau-de-bord/);
  await hr.getByRole('link', { name: 'Agents', exact: true }).click();
  await hr.getByLabel('Rechercher').fill(d.newcomer.name.split(' ')[1]!);
  const row = hr.getByRole('button', { name: new RegExp(d.newcomer.name) });
  await expect(row).toContainText('à inviter');
  await row.click();

  const invited = hr.waitForResponse((r) => r.url().includes('/invite/') && r.ok());
  await hr.getByRole('button', { name: 'Inviter l’agent' }).click();
  const { link, username } = (await (await invited).json()) as { link: string; username: string };
  expect(username).toBe(d.newcomer.username);
  await expect(hr.getByRole('img', { name: "Lien d'activation de l'agent" })).toBeVisible();
  await expect(row).toContainText('invité');

  // The agent opens the link on their phone (scanned from the QR or received by e-mail).
  const agent = await phone(browser, d);
  await agent.page.goto(new URL(link).pathname + new URL(link).search);
  await expect(agent.page.getByRole('heading', { name: 'Bonjour Awa' })).toBeVisible();
  await expect(agent.page.getByText(username)).toBeVisible();
  await agent.page.getByLabel('Mot de passe', { exact: true }).fill('Ma-cle-de-pointage-2026');
  await agent.page.getByLabel('Confirmez le mot de passe').fill('Ma-cle-de-pointage-2026');
  await agent.page.getByRole('button', { name: 'Activer mon accès' }).click();
  await expect(agent.page).toHaveURL(/\/agent/);
  await expect(agent.page.getByRole('button', { name: 'Activer ce téléphone' })).toBeVisible();

  // The same link cannot be used a second time.
  const other = await browser.newContext();
  const replay = await other.newPage();
  await replay.goto(new URL(link).pathname + new URL(link).search);
  await expect(replay.getByRole('heading', { name: 'Lien inutilisable' })).toBeVisible();

  await Promise.all([hrContext.close(), agent.context.close(), other.close()]);
});
