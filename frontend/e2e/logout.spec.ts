// TC13: log out from the account menu (see TEST-CASES.md).
// Logs in on its own (fresh browser), so logging out doesn't end the shared session other tests use.
import { expect, test } from '@playwright/test';
import { loginUI, settle } from './helpers';

test.use({ storageState: { cookies: [], origins: [] } });

test('TC13 logout works and ends the session', async ({ page }) => {
  await loginUI(page, process.env.E2E_EMAIL!, process.env.E2E_PASSWORD!);
  await expect(page).toHaveURL(/\/(admin|employee)\/dashboard/, { timeout: 60_000 });
  await settle(page);

  await page.getByRole('button', { name: /^Account: / }).click();
  await page.locator('#account-menu').getByRole('button', { name: 'Log out' }).click();

  const popup = page.getByRole('dialog');
  await expect(popup.getByText(/See you soon/)).toBeVisible();
  await popup.getByRole('button', { name: 'Log out' }).click();

  await expect(page).toHaveURL(/\/employee\/login/);
  await expect(page.getByText("You've logged out safely")).toBeVisible();

  await page.goto('/employee/dashboard');
  await expect(page).toHaveURL(/\/employee\/login/);
});
