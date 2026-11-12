// Shared bits for the live-site tests: who is testing, and logging in through the real login page.
import { expect, type Page, type TestInfo } from '@playwright/test';

export type Me = { id: number; name: string; email: string; role: 'admin' | 'employee'; permissions: string[]; modules?: Record<string, boolean> };

export function tester(info: TestInfo): string {
  return String(info.project.metadata.tester);
}

/** Email + password for this tester from .env.e2e.local. Missing: the test is skipped, not failed. */
export function login(info: TestInfo): { email: string; password: string } | null {
  const t = tester(info);
  const email = process.env[`E2E_EMAIL_${t}`];
  const password = process.env[`E2E_PASSWORD_${t}`] || process.env.E2E_PASSWORD;
  return email && password ? { email, password } : null;
}

/** Wakes the Render server up (free plan sleeps), so the first real page doesn't time out. */
export async function wakeServer(page: Page) {
  const r = await page.request.get('/api/health', { timeout: 75_000 });
  expect(r.ok(), `API health answered ${r.status()}`).toBeTruthy();
}

/** Logs in through the real form and waits for the portal. */
export async function logIn(page: Page, email: string, password: string) {
  await page.goto('/employee/login');
  await page.getByLabel('Work email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Log in', exact: true }).last().click();
  await expect(page).toHaveURL(/\/(admin|employee)\/dashboard/, { timeout: 45_000 });
}
