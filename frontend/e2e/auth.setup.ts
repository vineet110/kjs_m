// TC01 + TC02: wake the API, then log in ONCE and save the session for every other test.
import { expect, test as setup } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { loginUI, STORAGE } from './helpers';

setup.describe.configure({ mode: 'serial' });

setup('TC01 API health warm-up', async ({ request }) => {
  setup.setTimeout(90_000);
  const res = await request.get('/api/health', { timeout: 60_000 });
  expect(res.status()).toBe(200);
  expect(await res.json()).toMatchObject({ status: 'ok' });
});

setup('TC02 log in once and save the session', async ({ page }) => {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  expect(email && password, 'Create frontend/.env.e2e.local with E2E_EMAIL and E2E_PASSWORD').toBeTruthy();

  await loginUI(page, email!, password!);
  await expect(page).toHaveURL(/\/(admin|employee)\/dashboard/, { timeout: 60_000 });

  mkdirSync(path.dirname(STORAGE), { recursive: true });
  await page.context().storageState({ path: STORAGE });
});
