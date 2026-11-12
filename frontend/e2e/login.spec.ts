// TC03 - TC07: login, session and the dashboard (see TEST-CASES.md).
import { expect, test } from '@playwright/test';
import { ERROR_SCREENS, getMe, loginUI, settle, watch } from './helpers';

test.describe('not logged in', () => {
  test.use({ storageState: { cookies: [], origins: [] } }); // a fresh browser, no session

  test('TC03 portal page sends you to login', async ({ page }) => {
    await page.goto('/employee/dashboard');
    await expect(page).toHaveURL(/\/employee\/login\?next=%2Femployee%2Fdashboard/);
    await expect(page.getByRole('heading', { name: 'Staff portal' })).toBeVisible();
  });

  test('TC04 wrong login shows an error', async ({ page }) => {
    // A made-up address: never your own account, so it can't get locked
    await loginUI(page, 'nobody.e2e@example.com', 'wrong-password-123');
    await expect(page.locator('form p.bg-red-50')).toBeVisible();
    await expect(page).toHaveURL(/\/employee\/login/);
  });
});

test('TC05 logged in with this project\'s account', async ({ request }, info) => {
  const me = await getMe(request);
  const expected = String(info.project.metadata.email || '').toLowerCase();
  info.annotations.push({ type: 'account', description: `${me.email} | role ${me.role} | ${me.permissions.join(', ')}` });
  expect(me.email.toLowerCase(), `Project ${info.project.name} expects ${expected}`).toBe(expected);
});

test('TC06 dashboard loads with no errors', async ({ page, request }) => {
  const me = await getMe(request);
  const w = watch(page);
  const home = me.role === 'admin' ? '/admin/dashboard' : '/employee/dashboard';
  await page.goto(home);
  await settle(page);
  await expect(page).toHaveURL(new RegExp(home));
  await expect(page.getByText(ERROR_SCREENS)).toHaveCount(0);
  expect(w.crashes, 'page crashes').toEqual([]);
  expect(w.badApi, 'API answers 401/403/5xx').toEqual([]);
  expect(w.consoleErrors, 'console errors').toEqual([]);
});

test('TC07 account menu shows name, email and role', async ({ page, request }) => {
  const me = await getMe(request);
  await page.goto('/employee/dashboard');
  await settle(page);
  await page.getByRole('button', { name: `Account: ${me.name}` }).click();
  const menu = page.locator('#account-menu');
  await expect(menu).toBeVisible();
  await expect(menu.getByText(me.name, { exact: true })).toBeVisible();
  await expect(menu.getByText(me.email, { exact: true })).toBeVisible();
  await expect(menu.getByRole('button', { name: 'Log out' })).toBeVisible(); // seen, not clicked (TC13 does that)
});
