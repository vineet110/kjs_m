// Logs this tester in once and saves the session, so the other tests don't log in again
// (login is rate-limited, and the live site is shared by all three testers).
import { mkdirSync, writeFileSync } from 'node:fs';
import { test as setup, expect } from '@playwright/test';
import { login, logIn, tester, wakeServer } from './helpers';

setup('log in', async ({ page }, info) => {
  const creds = login(info);
  setup.skip(!creds, `No E2E_EMAIL_${tester(info)} in .env.e2e.local`);
  await wakeServer(page);
  await logIn(page, creds!.email, creds!.password);

  // Who am I: role, permissions, portal areas. Saved for the other tests.
  const r = await page.request.get('/api/v1/auth/me');
  expect(r.ok()).toBeTruthy();
  mkdirSync('../e2e-output/auth', { recursive: true });
  writeFileSync(`../e2e-output/auth/${tester(info)}.me.json`, JSON.stringify(await r.json(), null, 2));
  await page.context().storageState({ path: `../e2e-output/auth/${tester(info)}.json` });
});
