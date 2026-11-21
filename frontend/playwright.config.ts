import { defineConfig } from '@playwright/test';

/**
 * Browser end-to-end tests over the whole stack (API, kiosk, agent app, back-office).
 *   native : .\tasks.ps1 dev, then .\tasks.ps1 e2e        (http://localhost:4200)
 *   docker : E2E_BASE_URL=http://localhost:8080 E2E_PREPARE="docker compose exec -T -e POINTQR_E2E=1 backend python manage.py e2e_prepare" npx playwright test
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: process.env['CI'] ? 1 : 0,
  // In CI, failures also become annotations (readable without signing in to GitHub).
  reporter: process.env['CI'] ? [['list'], ['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env['E2E_BASE_URL'] ?? 'http://localhost:4200',
    locale: 'fr-FR',
    timezoneId: 'Africa/Abidjan',
    // Locally the installed Chrome is used (no browser download); CI installs Chromium.
    channel: process.env['CI'] ? undefined : 'chrome',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
