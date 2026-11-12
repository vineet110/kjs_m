// Read-only checks of the staff portal on the live site, as this tester (V, S or K).
// Nothing is created, edited or deleted. Checks are "soft": one broken page is recorded and the run
// carries on with the rest, so one report shows every problem.
import { existsSync, readFileSync } from 'node:fs';
import { test, expect, type Page } from '@playwright/test';
import { navFor } from '@/components/portal/SidebarNav';
import { login, logIn, tester, type Me } from './helpers';

function me(t: string): Me {
  return JSON.parse(readFileSync(`.auth/${t}.me.json`, 'utf8'));
}

test.beforeEach(async ({}, info) => {
  test.skip(!existsSync(`.auth/${tester(info)}.me.json`), 'Not logged in (see setup)');
});

/** The sidebar starts closed on some screens: open it with ☰ if needed. */
async function openSidebar(page: Page) {
  const menu = page.getByRole('button', { name: 'Open menu' });
  await expect(menu.or(page.getByRole('button', { name: 'Close menu' }).first())).toBeVisible();
  if (await menu.isVisible()) await menu.click();
}

/** Every link in the real sidebar: opens each group (only one stays open at a time) and reads its links. */
async function sidebarLinks(page: Page): Promise<string[]> {
  await openSidebar(page);
  const nav = page.getByRole('navigation', { name: 'Portal' });
  await expect(nav.locator('a').first()).toBeVisible();
  const hrefs = new Set<string>();
  const heads = nav.locator('button[aria-controls^="nav-"]');
  const n = await heads.count();
  if (n === 0) for (const h of await nav.locator('a').evaluateAll((as) => as.map((a) => a.getAttribute('href')))) hrefs.add(h!);
  for (let i = 0; i < n; i++) {
    const head = heads.nth(i);
    if ((await head.getAttribute('aria-expanded')) !== 'true') await head.click();
    const list = nav.locator(`#${await head.getAttribute('aria-controls')}`);
    for (const h of await list.locator('a').evaluateAll((as) => as.map((a) => a.getAttribute('href')))) hrefs.add(h!);
  }
  return [...hrefs].sort();
}

test('lands on the right dashboard for the role', async ({ page }, info) => {
  const m = me(tester(info));
  await page.goto('/employee/dashboard');
  if (m.role === 'admin') await page.goto('/admin/dashboard');
  await openSidebar(page);
  await expect(page.getByRole('navigation', { name: 'Portal' })).toBeVisible();
  await expect(page.getByText('Could not load your account')).toHaveCount(0);
  await expect(page.getByText(m.role === 'admin' ? 'KJS Admin' : 'KJS Portal', { exact: true })).toBeVisible();
});

test('sidebar shows exactly the pages this role may use', async ({ page }, info) => {
  const m = me(tester(info));
  await page.goto('/employee/dashboard');
  const shown = await sidebarLinks(page);
  const expected = navFor({ permissions: m.permissions, modules: m.modules })
    .flatMap((g) => g.items.map((i) => i.href))
    .sort();
  expect(shown).toEqual(expected);
});

test('every sidebar page opens without errors', async ({ page }, info) => {
  test.setTimeout(10 * 60_000);
  const m = me(tester(info));
  const pages = navFor({ permissions: m.permissions, modules: m.modules }).flatMap((g) => g.items.map((i) => i.href));

  let current = '';
  const problems: string[] = [];
  page.on('console', (msg) => msg.type() === 'error' && problems.push(`${current}: console error: ${msg.text().slice(0, 200)}`));
  page.on('pageerror', (e) => problems.push(`${current}: page crash: ${e.message.slice(0, 200)}`));
  page.on('response', (r) => {
    // A page this person may open should never get 403 (shown but refused) or a 5xx (server error)
    if (r.url().includes('/api/') && (r.status() >= 500 || r.status() === 403)) problems.push(`${current}: ${r.status()} ${new URL(r.url()).pathname}`);
  });

  for (const href of pages) {
    await test.step(href, async () => {
      current = href;
      await page.goto(href);
      await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => undefined); // chat may keep polling
      await expect.soft(page.getByText('Could not load your account'), `${href}: account error`).toHaveCount(0);
      await expect.soft(page.getByText('Not available yet', { exact: true }), `${href}: switched off but in the menu`).toHaveCount(0);
      await expect.soft(page.getByText('Application error'), `${href}: crashed`).toHaveCount(0);
      // Attendance is a full-screen workspace with no page title
      if (href !== '/employee/attendance') await expect.soft(page.locator('h1').first(), `${href}: no page title`).toBeVisible();
    });
  }
  // Listed together at the end, so every page was visited first
  expect.soft(problems, 'console errors / refused / server errors').toEqual([]);
});

test('admin-only API refuses non-admins', async ({ page }, info) => {
  const m = me(tester(info));
  const r = await page.request.get('/api/v1/admin/users');
  expect(r.status()).toBe(m.permissions.includes('staff.approve') ? 200 : 403);
});

test('logout works', async ({ browser }, info) => {
  // Its own fresh login: logging out the saved session would log out the other tests too
  const creds = login(info)!;
  const ctx = await browser.newContext({ storageState: undefined });
  const page = await ctx.newPage();
  await logIn(page, creds.email, creds.password);
  await openSidebar(page);
  await page.locator('#portal-sidebar').getByRole('button', { name: 'Log out' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Log out' }).click();
  await expect(page).toHaveURL(/\/employee\/login/);
  await expect(page.getByText("You've logged out safely")).toBeVisible();
  const after = await page.request.get('/api/v1/auth/me');
  expect(after.status()).toBe(401);
  await ctx.close();
});
