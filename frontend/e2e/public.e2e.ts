import { expect, test } from '@playwright/test';

test('le site vitrine se charge et mène à la connexion', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText(
    'Le pointage qui ne ment pas.',
  );
  await page.getByRole('link', { name: 'Se connecter' }).click();
  await expect(page).toHaveURL(/\/connexion/);
  await expect(page.getByRole('button', { name: 'Se connecter' })).toBeVisible();
});

test('un mauvais mot de passe est refusé avec un message clair', async ({ page }) => {
  await page.goto('/connexion');
  await page.getByLabel('Code entreprise').fill('E2ETEST');
  await page.getByLabel('Identifiant').fill('inconnu');
  await page.getByLabel('Mot de passe').fill('mauvais-mot-de-passe');
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL(/\/connexion/);
});
