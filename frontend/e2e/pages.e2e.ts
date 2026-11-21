import { type Page, expect, test } from '@playwright/test';

import { type E2EData, data, signIn, signInWithTotp } from './support';

/**
 * Every page of every role's menu opens without a JavaScript error, a server error or a
 * forbidden API call, and shows its title. Catches broken screens and wrong permissions.
 */
const PAGES: Record<string, { label: string; path: string }[]> = {};
const ALL = {
  dashboard: { label: 'Tableau de bord', path: '/app/tableau-de-bord' },
  checkins: { label: 'Pointages', path: '/app/pointages' },
  requests: { label: 'Demandes', path: '/app/demandes' },
  reports: { label: 'Rapports', path: '/app/rapports' },
  agents: { label: 'Agents', path: '/app/agents' },
  org: { label: 'Organigramme', path: '/app/organisation' },
  sites: { label: 'Sites', path: '/app/sites' },
  schedules: { label: 'Horaires', path: '/app/horaires' },
  kiosks: { label: 'Bornes', path: '/app/bornes' },
  devices: { label: 'Téléphones', path: '/app/telephones' },
  users: { label: 'Utilisateurs', path: '/app/utilisateurs' },
  audit: { label: "Journal d'audit", path: '/app/audit' },
  settings: { label: 'Paramètres', path: '/app/parametres' },
};
PAGES['admin'] = Object.values(ALL);
PAGES['hr'] = [
  ALL.dashboard,
  ALL.checkins,
  ALL.requests,
  ALL.reports,
  ALL.agents,
  ALL.org,
  ALL.sites,
  ALL.schedules,
  ALL.devices,
  ALL.settings,
];
PAGES['manager'] = [
  ALL.dashboard,
  ALL.checkins,
  ALL.requests,
  ALL.agents,
  ALL.org,
  ALL.sites,
  ALL.settings,
];
PAGES['auditor'] = [
  ALL.dashboard,
  ALL.checkins,
  ALL.requests,
  ALL.reports,
  ALL.agents,
  ALL.org,
  ALL.sites,
  ALL.schedules,
  ALL.kiosks,
  ALL.audit,
  ALL.settings,
];

function watch(page: Page): string[] {
  const problems: string[] = [];
  page.on('pageerror', (e) => problems.push(`JS: ${e.message}`));
  page.on('response', (r) => {
    const url = r.url();
    if (!url.includes('/api/')) return;
    if (url.includes('/auth/refresh/') && r.status() === 401) return; // no session yet
    if (r.status() >= 500 || r.status() === 403 || r.status() === 404) {
      problems.push(
        `HTTP ${r.status()} ${r.request().method()} ${url.replace(/^https?:\/\/[^/]+/, '')}`,
      );
    }
  });
  return problems;
}

for (const role of Object.keys(PAGES)) {
  test(`chaque page du menu « ${role} » s'ouvre sans erreur`, async ({ browser }) => {
    test.setTimeout(150_000);
    const d: E2EData = data();
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const page = await context.newPage();
    const problems = watch(page);
    const username = d.staff[role as keyof E2EData['staff']];
    if (role === 'admin' || role === 'hr') await signInWithTotp(page, d, username);
    else await signIn(page, d, username);
    await expect(page).toHaveURL(/\/app\//);

    const nav = page.locator('aside[aria-label="Navigation principale"]');
    const links = (await nav.getByRole('link').allInnerTexts())
      .map((t) => t.trim())
      .filter((t) => t && t !== 'PointQR'); // the logo links home
    expect(links.sort()).toEqual(PAGES[role]!.map((p) => p.label).sort());

    for (const target of PAGES[role]!) {
      await nav.getByRole('link', { name: target.label, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(target.path));
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await page.waitForLoadState('networkidle');
    }
    expect(problems, problems.join('\n')).toEqual([]);
    await context.close();
  });
}
