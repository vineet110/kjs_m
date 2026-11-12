// Admin module, end to end, on the live site. One test per case in docs/testing/admin-e2e.xlsx: each test
// title starts with its case ID, and scripts/e2e/admin_workbook.py copies the results into the workbook.
// Scope (b): look at everything; create and remove only "E2E" test data; shared settings are never saved.
// Tests run in order in one worker. A failing test doesn't stop the rest; each change test finds its
// test data by name, so it still works after an earlier test failed.
import { readFileSync } from 'node:fs';
import { test, expect, type Page } from '@playwright/test';
import { logIn, login, type Me } from './helpers';

const E2E_EMAIL = 'e2e.user@kjs-e2e.test';
const NEXT_YEAR = new Date().getFullYear() + 1;
const HOLIDAY = 'E2E Holiday';
const HOLIDAY_DAY = `${NEXT_YEAR}-12-30`;
const OFFER = 'E2E Offer (test, deleted at once)';
const SOURCE = 'E2E Source';
const PRODUCT = 'E2E Product';
const BOARD_NAME = 'E2E Board (test)';

const me = (): Me => JSON.parse(readFileSync('.auth/A.me.json', 'utf8'));

// Every confirm() popup (Remove?, Delete?, Mark done?) is answered "OK"
test.beforeEach(async ({ page }) => {
  page.on('dialog', (d) => d.accept());
});

async function get<T>(page: Page, path: string): Promise<T> {
  const r = await page.request.get(`/api/v1${path}`);
  expect(r.ok(), `GET ${path} answered ${r.status()}`).toBeTruthy();
  return r.json();
}

async function openSidebar(page: Page) {
  const menu = page.getByRole('button', { name: 'Open menu' });
  await expect(menu.or(page.getByRole('button', { name: 'Close menu' }).first())).toBeVisible();
  if (await menu.isVisible()) await menu.click();
}

const title = (page: Page, text: string) => expect(page.getByRole('heading', { level: 1, name: text })).toBeVisible();

// ---------------------------------------------------------------- Login and access
test.describe('Login & access', () => {
  test('ADM-001 Admin logs in', async ({ browser }) => {
    const creds = login(test.info())!;
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await logIn(page, creds.email, creds.password);
    await expect(page).toHaveURL(/\/admin\/dashboard/);
    await openSidebar(page);
    await expect(page.getByText('Admin console')).toBeVisible();
    await ctx.close();
  });

  test('ADM-002 Wrong password is refused', async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await page.goto('/employee/login');
    await page.getByLabel('Work email').fill(login(test.info())!.email);
    await page.getByLabel('Password').fill('wrong-password-e2e');
    await page.getByRole('button', { name: 'Log in', exact: true }).last().click();
    await expect(page.locator('p.bg-red-50')).toBeVisible({ timeout: 30_000 });
    await expect(page).toHaveURL(/\/employee\/login/);
    expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);
    await ctx.close();
  });

  test('ADM-003 Logged-out visitor cannot open admin pages', async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await page.goto('/admin/dashboard');
    await expect(page).toHaveURL(/\/employee\/login\?next=%2Fadmin%2Fdashboard/);
    await ctx.close();
  });

  test('ADM-004 Employee without staff.approve is refused by the admin API', async ({ browser }) => {
    const email = process.env.E2E_EMAIL_V;
    const password = process.env.E2E_PASSWORD_V || process.env.E2E_PASSWORD;
    test.skip(!email || !password, 'No login for tester V in .env.e2e.local');
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await logIn(page, email!, password!);
    const v = await (await page.request.get('/api/v1/auth/me')).json();
    test.skip(v.permissions.includes('staff.approve'), 'Tester V has staff.approve now; pick another employee');
    expect((await page.request.get('/api/v1/admin/users')).status()).toBe(403);
    await ctx.close();
  });

  test('ADM-005 Admin sidebar shows every admin group', async ({ page }) => {
    await page.goto('/admin/dashboard');
    await openSidebar(page);
    const nav = page.getByRole('navigation', { name: 'Portal' });
    for (const g of ['My work', 'Lead Management', 'Dashboard', 'Employees', 'Order Boards & Assigning', 'Global Site', 'Reports & settings']) {
      await expect.soft(nav.getByRole('button', { name: g, exact: false }).last(), `group ${g}`).toBeVisible();
    }
  });

  test('ADM-006 Logout ends the session', async ({ browser }) => {
    const creds = login(test.info())!;
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    page.on('dialog', (d) => d.accept());
    await logIn(page, creds.email, creds.password);
    await openSidebar(page);
    await page.locator('#portal-sidebar').getByRole('button', { name: 'Log out' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Log out' }).click();
    await expect(page.getByText("You've logged out safely")).toBeVisible();
    expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);
    await ctx.close();
  });
});

// ---------------------------------------------------------------- Admin overview
test.describe('Admin overview', () => {
  test.use({ reducedMotion: 'reduce' }); // tiles show their final number at once (no count-up)

  test('ADM-010 Stat tiles show', async ({ page }) => {
    await page.goto('/admin/dashboard');
    for (const label of ['New leads', 'Leads this week', 'All leads', 'Waiting for approval', 'Active staff', 'Products']) {
      await expect.soft(page.getByText(label, { exact: true }).first(), label).toBeVisible();
    }
  });

  test('ADM-011 Tile numbers match the server', async ({ page }) => {
    const s = await get<Record<string, number | null>>(page, '/admin/stats');
    await page.goto('/admin/dashboard');
    const tile = (label: string) => page.locator('a, div').filter({ has: page.getByText(label, { exact: true }) }).last().locator('..');
    const pairs: [string, unknown][] = [
      ['New leads', s.leads_new], ['Leads this week', s.leads_this_week], ['All leads', s.leads_total],
      ['Waiting for approval', s.staff_pending], ['Active staff', s.staff_active], ['Products', s.products],
    ];
    for (const [label, value] of pairs) {
      if (value === null || value === undefined) continue;
      await expect.soft(tile(label), `${label} = ${value}`).toContainText(String(value));
    }
  });

  test('ADM-012 Waiting sign-ups list or empty message', async ({ page }) => {
    await page.goto('/admin/dashboard');
    const s = await get<{ staff_pending: number }>(page, '/admin/stats');
    if (s.staff_pending === 0) await expect(page.getByText('All caught up!')).toBeVisible();
    else await expect(page.getByRole('button', { name: /Approve/ }).first()).toBeVisible();
  });
});

// ---------------------------------------------------------------- All Enquiries
test.describe('All Enquiries', () => {
  test('ADM-020 Enquiries list loads', async ({ page }) => {
    const leads = await get<{ name: string }[]>(page, '/admin/leads');
    await page.goto('/admin/leads');
    await title(page, 'All Enquiries');
    // Enquiries show as cards: the newest one's name must be on the page
    if (leads.length > 0) await expect(page.getByText(leads[0].name, { exact: false }).first()).toBeVisible();
    test.info().annotations.push({ type: 'note', description: `${leads.length} enquiries listed.` });
  });

  test('ADM-021 SLA times shown match settings', async ({ page }) => {
    const sla = await get<{ respond_minutes: number; resolve_minutes: number }>(page, '/admin/sla');
    await page.goto('/admin/leads');
    await expect(page.getByText(`respond in ${sla.respond_minutes} min, close in ${sla.resolve_minutes} min`)).toBeVisible();
  });

  test('ADM-022 SLA filter narrows the list', async ({ page }) => {
    await page.goto('/admin/leads');
    const all = await get<unknown[]>(page, '/admin/leads');
    const overdue = await get<unknown[]>(page, '/admin/leads?sla=overdue');
    const filter = page.locator('select').filter({ has: page.locator('option', { hasText: 'Any SLA' }) });
    const answer = page.waitForResponse((r) => r.url().includes('sla=overdue'));
    await filter.selectOption('overdue');
    expect((await answer).ok()).toBeTruthy();
    expect(overdue.length).toBeLessThanOrEqual(all.length);
    test.info().annotations.push({ type: 'note', description: `${overdue.length} overdue of ${all.length} enquiries.` });
  });
});

// ---------------------------------------------------------------- Approvals
test.describe('Approvals', () => {
  test('ADM-030 Approvals inbox loads', async ({ page }) => {
    await page.goto('/admin/approvals');
    await title(page, 'All approvals');
    for (const h of ['New staff', 'Missed punches', 'File delete requests']) {
      await expect.soft(page.getByRole('heading', { name: new RegExp(`^${h} \\(\\d+\\)`) }), h).toBeVisible();
    }
  });

  test('ADM-031 Sidebar badge matches the inbox', async ({ page }) => {
    const inbox = await get<{ signups: unknown[] | null; regularizations: unknown[] | null; file_deletes: unknown[] | null }>(page, '/admin/approvals');
    const n = (inbox.signups?.length ?? 0) + (inbox.regularizations?.length ?? 0) + (inbox.file_deletes?.length ?? 0);
    await page.goto('/admin/approvals');
    await openSidebar(page);
    const link = page.getByRole('navigation', { name: 'Portal' }).getByRole('link', { name: /All approvals/ });
    if (n === 0) await expect(link).not.toContainText(/\d/);
    else await expect(link).toContainText(n > 99 ? '99+' : String(n));
  });
});

// ---------------------------------------------------------------- Manage employees
test.describe('Manage employees', () => {
  type U = { id: number; name: string; email: string; status: string; branch: string };
  const e2eUser = async (page: Page) => (await get<U[]>(page, '/admin/users')).find((u) => u.email === E2E_EMAIL);

  test('ADM-040 Staff list loads', async ({ page }) => {
    await page.goto('/admin/users');
    await title(page, 'Manage employees');
    for (const col of ['Name', 'Email', 'Role', 'Status']) await expect.soft(page.getByRole('columnheader', { name: col, exact: true })).toBeVisible();
  });

  test('ADM-041 Search in the staff list', async ({ page }) => {
    await page.goto('/admin/users');
    await page.getByPlaceholder('Search').fill(me().email);
    await expect(page.getByRole('cell', { name: me().email })).toBeVisible();
    await page.getByPlaceholder('Search').fill('zz-no-such-person-zz');
    await expect(page.getByText('Nothing matches your search')).toBeVisible();
  });

  test('ADM-042 New employee form checks required fields', async ({ page }) => {
    await page.goto('/admin/users/new');
    await page.getByRole('button', { name: 'Submit' }).click();
    await expect(page.locator('#u-name')).toHaveJSProperty('validity.valueMissing', true);
    await expect(page.getByText('can log in now')).toHaveCount(0);
  });

  test('ADM-043 Create test employee', async ({ page }) => {
    if (await e2eUser(page)) {
      test.info().annotations.push({ type: 'note', description: 'E2E user already existed from an earlier run; reused.' });
      return;
    }
    await page.goto('/admin/users/new');
    await page.locator('#u-name').fill('E2E Test User');
    await page.locator('#u-email').fill(E2E_EMAIL);
    await page.locator('#u-phone').fill('9876500000');
    await page.locator('#u-code').fill('E2E-001');
    await page.locator('#u-branch').fill('Main Branch');
    await page.locator('#u-role').selectOption('employee');
    await page.getByRole('button', { name: 'Submit' }).click();
    await expect(page.getByText('E2E Test User can log in now')).toBeVisible();
    expect(await e2eUser(page)).toBeTruthy();
  });

  test('ADM-044 Duplicate email refused', async ({ page }) => {
    test.skip(!(await e2eUser(page)), 'Needs the E2E user (ADM-043)');
    await page.goto('/admin/users/new');
    await page.locator('#u-name').fill('E2E Duplicate');
    await page.locator('#u-email').fill(E2E_EMAIL);
    await page.locator('#u-phone').fill('9876500001');
    await page.locator('#u-code').fill('E2E-002');
    await page.locator('#u-branch').fill('Main Branch');
    await page.locator('#u-role').selectOption('employee');
    await page.getByRole('button', { name: 'Submit' }).click();
    await expect(page.locator('form').getByText(/already|exists|taken|in use/i)).toBeVisible();
    expect((await get<U[]>(page, '/admin/users')).filter((u) => u.email === E2E_EMAIL)).toHaveLength(1);
  });

  test('ADM-045 Edit the test employee', async ({ page }) => {
    const u = await e2eUser(page);
    test.skip(!u, 'Needs the E2E user (ADM-043)');
    const branch = u!.branch === 'E2E Branch' ? 'Main Branch' : 'E2E Branch';
    await page.goto(`/admin/users/${u!.id}`);
    await page.locator('#u-branch').fill(branch);
    await page.getByRole('button', { name: 'Submit' }).click();
    await expect(page.getByText('Saved.')).toBeVisible();
    expect((await e2eUser(page))!.branch).toBe(branch);
  });

  test('ADM-046 Disable the test employee', async ({ page }) => {
    const u = await e2eUser(page);
    test.skip(!u, 'Needs the E2E user (ADM-043)');
    if (u!.status !== 'disabled') {
      await page.goto('/admin/dashboard');
      const row = page.locator('tr').filter({ hasText: E2E_EMAIL });
      await row.getByRole('button', { name: 'Disable' }).click();
      await expect(row.getByRole('button', { name: 'Enable' })).toBeVisible();
    }
    expect((await e2eUser(page))!.status).toBe('disabled');
  });
});

// ---------------------------------------------------------------- Attendance
test.describe('Attendance', () => {
  test('ADM-050 Team attendance for today', async ({ page }) => {
    await page.goto('/admin/team-attendance');
    await title(page, 'Attendance');
    await expect(page.getByRole('heading', { name: /Roster$/ })).toBeVisible();
  });

  test('ADM-051 Another day', async ({ page }) => {
    await page.goto('/admin/team-attendance');
    const before = await page.getByRole('heading', { name: /Roster$/ }).textContent();
    const answer = page.waitForResponse((r) => r.url().includes('/attendance/team?day='));
    await page.getByRole('button', { name: '←' }).click();
    expect((await answer).ok()).toBeTruthy();
    await expect(page.getByRole('heading', { name: /Roster$/ })).not.toHaveText(before!);
  });

  test('ADM-052 Approval lists show', async ({ page }) => {
    await page.goto('/admin/team-attendance');
    await expect(page.locator('h2')).not.toHaveCount(0);
    const h2 = (await page.locator('h2').allTextContents()).join(' | ');
    test.info().annotations.push({ type: 'note', description: `Sections: ${h2.replace(/\s+/g, ' ')}` });
    expect(h2).toMatch(/leave/i);
    expect(h2).toMatch(/punch|regulari|correction/i);
  });

  test('ADM-053 Export to Excel', async ({ page }) => {
    await page.goto('/admin/team-attendance');
    await page.getByRole('button', { name: /Export to Excel/ }).click();
    const download = page.waitForEvent('download', { timeout: 60_000 });
    await page.getByRole('button', { name: 'Download .xlsx Report' }).click();
    expect((await download).suggestedFilename()).toMatch(/\.xlsx$/);
  });
});

// ---------------------------------------------------------------- Holidays
test.describe('Holidays', () => {
  type H = { id: number; name: string; day: string };
  const ours = async (page: Page) => (await get<H[]>(page, `/admin/holidays?year=${NEXT_YEAR}`)).filter((h) => h.name === HOLIDAY);

  test('ADM-060 Holiday list for this year', async ({ page }) => {
    await page.goto('/admin/holidays');
    await title(page, 'Holidays');
    await expect(page.getByText(String(new Date().getFullYear()), { exact: true })).toBeVisible();
  });

  test('ADM-061 Switch year', async ({ page }) => {
    await page.goto('/admin/holidays');
    const answer = page.waitForResponse((r) => r.url().includes(`/admin/holidays?year=${NEXT_YEAR}`));
    await page.getByRole('button', { name: '→' }).click();
    expect((await answer).ok()).toBeTruthy();
    await expect(page.getByText(String(NEXT_YEAR), { exact: true })).toBeVisible();
  });

  test('ADM-062 Add a test holiday', async ({ page }) => {
    for (const h of await ours(page)) await page.request.delete(`/api/v1/admin/holidays/${h.id}`, { headers: { 'x-requested-with': 'kjs' } });
    await page.goto('/admin/holidays');
    await page.locator('input[name="day"]').fill(HOLIDAY_DAY);
    await page.locator('input[name="name"]').fill(HOLIDAY);
    await page.getByRole('button', { name: 'Add holiday' }).click();
    await expect(page.getByText(`Added ${HOLIDAY} to the holidays`)).toBeVisible();
    await page.getByRole('button', { name: '→' }).click();
    await expect(page.getByText(HOLIDAY, { exact: true })).toBeVisible();
  });

  test('ADM-063 Holiday without a name is refused', async ({ page }) => {
    await page.goto('/admin/holidays');
    await page.locator('input[name="day"]').fill(HOLIDAY_DAY);
    await page.getByRole('button', { name: 'Add holiday' }).click();
    await expect(page.locator('input[name="name"]')).toHaveJSProperty('validity.valueMissing', true);
    await expect(page.getByText(/^Added /)).toHaveCount(0);
  });

  test('ADM-064 Delete the test holiday', async ({ page }) => {
    test.skip((await ours(page)).length === 0, 'Needs the E2E holiday (ADM-062)');
    await page.goto('/admin/holidays');
    await page.getByRole('button', { name: '→' }).click();
    const row = page.locator('div').filter({ hasText: HOLIDAY }).filter({ has: page.getByRole('button', { name: 'Remove' }) }).last();
    await row.getByRole('button', { name: 'Remove' }).click();
    await expect(page.getByText(HOLIDAY, { exact: true })).toHaveCount(0);
    expect(await ours(page)).toHaveLength(0);
  });
});

// ---------------------------------------------------------------- Order boards
test.describe('Order boards', () => {
  type B = { code: string; name: string; final_status: string | null };
  const ourBoards = async (page: Page, finished: boolean) =>
    (await get<B[]>(page, `/boards?include_finished=${finished}`)).filter((b) => b.name === BOARD_NAME);
  const running = async (page: Page) => (await ourBoards(page, false)).find((b) => !b.final_status);

  test('ADM-070 Boards list loads', async ({ page }) => {
    await page.goto('/admin/order-boards');
    await title(page, 'All order boards');
    const answer = page.waitForResponse((r) => r.url().includes('include_finished=true'));
    await page.getByLabel('Show finished').check();
    expect((await answer).ok()).toBeTruthy();
  });

  test('ADM-071 Create a test board', async ({ page }) => {
    if (await running(page)) {
      test.info().annotations.push({ type: 'note', description: 'A running E2E board existed from an earlier run; reused.' });
      return;
    }
    const code = `E2E-${Date.now().toString().slice(-6)}`;
    const today = new Date().toISOString().slice(0, 10);
    const later = new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10);
    await page.goto('/admin/order-boards');
    await page.getByRole('button', { name: 'New board' }).click();
    await page.getByPlaceholder('ABC117-3').fill(code);
    await page.getByPlaceholder('3-in-1 coffee sticks, 18 g').fill(BOARD_NAME);
    const form = page.locator('form').filter({ has: page.getByPlaceholder('ABC117-3') });
    await form.locator('div:has(> label:text-is("Client")) input').fill('E2E Client');
    await form.locator('div:has(> label:text-is("Start")) input').fill(today);
    await form.locator('div:has(> label:text-is("Deadline")) input').fill(later);
    // Only the admin on each step: nobody else gets tasks or alerts
    for (let i = 1; i <= 3; i++) {
      await page.getByRole('list', { name: `People on step ${i}` }).getByRole('checkbox', { name: me().name }).check();
    }
    await page.getByRole('button', { name: 'Create board' }).click();
    await expect.poll(async () => !!(await running(page)), { timeout: 30_000 }).toBeTruthy();
    test.info().annotations.push({ type: 'note', description: `Board ${code} created.` });
  });

  test('ADM-072 Open the board', async ({ page }) => {
    const b = await running(page);
    test.skip(!b, 'Needs the E2E board (ADM-071)');
    await page.goto(`/admin/order-boards/${b!.code}`);
    for (const tab of [/^Steps/, /^Files/, /^People/, /^History/]) await expect.soft(page.getByRole('tab', { name: tab })).toBeVisible();
    await page.getByRole('tab', { name: /^History/ }).click();
    await expect(page.getByRole('tab', { name: /^History/ })).toHaveAttribute('aria-selected', 'true');
  });

  test('ADM-073 Mark a step done', async ({ page }) => {
    const b = await running(page);
    test.skip(!b, 'Needs the E2E board (ADM-071)');
    await page.goto(`/admin/order-boards/${b!.code}`);
    await page.getByRole('button', { name: 'Mark step done' }).first().click();
    await expect(page.getByText(/"Sourcing" done/)).toBeVisible();
  });

  test('ADM-074 Finish the test board', async ({ page }) => {
    const b = await running(page);
    test.skip(!b, 'Needs the E2E board (ADM-071)');
    await page.goto(`/admin/order-boards/${b!.code}`);
    await page.getByRole('button', { name: 'Cancelled', exact: true }).click();
    await expect(page.getByText('Board marked Cancelled')).toBeVisible();
    expect(await running(page)).toBeFalsy();
  });
});

// ---------------------------------------------------------------- Auto-assign
test.describe('Auto-assign', () => {
  test('ADM-080 Overview loads', async ({ page }) => {
    await page.goto('/admin/auto-assign');
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Preview' })).toBeVisible();
  });

  test('ADM-081 Preview without running', async ({ page }) => {
    await page.goto('/admin/auto-assign');
    const answer = page.waitForResponse((r) => r.url().includes('/assign/preview'));
    await page.getByRole('button', { name: 'Preview' }).click();
    const r = await answer;
    expect(r.status(), 'preview answered').toBeLessThan(500);
    test.info().annotations.push({ type: 'note', description: `Preview answered ${r.status()}. "Run now" was not clicked.` });
  });
});

// ---------------------------------------------------------------- Client Schedulers
test.describe('Client Schedulers', () => {
  type Src = { id: number; name: string };
  const ourSources = async (page: Page) => (await get<Src[]>(page, '/admin/harvest/sources')).filter((s) => s.name === SOURCE);

  async function fillSource(page: Page, url: string) {
    await page.getByRole('button', { name: '+ Add New Source' }).click();
    await page.getByPlaceholder('e.g. IndiaMART Spices Directory').fill(SOURCE);
    await page.locator('select').filter({ has: page.locator('option[value="rss"]') }).selectOption('rss');
    await page.getByPlaceholder('https://api.indiamart.com/buyer-enquiries').fill(url);
    await page.locator('#modal_is_active').uncheck(); // never runs on its own
  }

  test('ADM-090 Page loads', async ({ page }) => {
    await page.goto('/admin/client-schedulers');
    await title(page, 'Client Schedulers (Lead Harvester)');
    await expect(page.getByRole('heading', { name: 'Configured Sources & Schedulers' })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Recent Ingestion/ })).toBeVisible();
  });

  test('ADM-091 Add a test source', async ({ page }) => {
    for (const s of await ourSources(page)) await page.request.delete(`/api/v1/admin/harvest/sources/${s.id}`, { headers: { 'x-requested-with': 'kjs' } });
    await page.goto('/admin/client-schedulers');
    await fillSource(page, 'https://example.com/e2e-feed.xml');
    await page.getByRole('button', { name: 'Create Source' }).click();
    await expect(page.getByRole('cell', { name: SOURCE }).first()).toBeVisible();
    expect(await ourSources(page)).toHaveLength(1);
  });

  test('ADM-092 Unsafe address refused', async ({ page }) => {
    const before = (await ourSources(page)).length;
    await page.goto('/admin/client-schedulers');
    await fillSource(page, 'http://localhost/feed.xml');
    await page.getByRole('button', { name: 'Create Source' }).click();
    await expect(page.locator('.bg-red-50, [role="alert"]').first()).toBeVisible();
    expect(await ourSources(page)).toHaveLength(before);
  });

  test('ADM-093 Delete the test source', async ({ page }) => {
    test.skip((await ourSources(page)).length === 0, 'Needs the E2E source (ADM-091)');
    await page.goto('/admin/client-schedulers');
    await page.locator('tr').filter({ hasText: SOURCE }).first().getByRole('button', { name: 'Delete' }).click();
    await expect(page.locator('tr').filter({ hasText: SOURCE })).toHaveCount(0);
    expect(await ourSources(page)).toHaveLength(0);
  });
});

// ---------------------------------------------------------------- Products
test.describe('Products', () => {
  type P = { id: number; name: string; slug: string; is_active: boolean; description: string };
  const ourProduct = async (page: Page) => (await get<P[]>(page, '/admin/products')).find((p) => p.name === PRODUCT);

  test('ADM-100 Product list loads', async ({ page }) => {
    await page.goto('/admin/products');
    await title(page, 'All Products');
    await expect(page.getByRole('heading', { name: 'Add a product' })).toBeVisible();
  });

  test('ADM-101 Create a hidden test product', async ({ page }) => {
    let p = await ourProduct(page);
    await page.goto('/admin/products');
    if (!p) {
      const form = page.locator('form').filter({ has: page.getByRole('heading', { name: 'Add a product' }) });
      await form.getByPlaceholder('Instant Coffee 3-in-1 Stick').fill(PRODUCT);
      await form.locator('textarea[name="description"]').fill('E2E test product. Hidden; not for sale.');
      await form.getByRole('checkbox', { name: 'Private label' }).uncheck();
      await form.getByRole('button', { name: 'Add product' }).click();
      await expect(page.getByText(`Added "${PRODUCT}"`)).toBeVisible();
      p = await ourProduct(page);
      expect(p, 'saved').toBeTruthy();
    } else test.info().annotations.push({ type: 'note', description: 'E2E product existed from an earlier run; reused.' });
    if (p!.is_active) {
      // A new product is live at once: hide it straight away
      await page.reload();
      await page.locator('div.space-y-2').filter({ hasText: PRODUCT }).getByRole('button', { name: 'Hide' }).click();
      await expect.poll(async () => (await ourProduct(page))!.is_active).toBe(false);
    }
  });

  test('ADM-102 Edit the test product', async ({ page }) => {
    const p = await ourProduct(page);
    test.skip(!p, 'Needs the E2E product (ADM-101)');
    const text = `E2E test product, edited ${new Date().toISOString().slice(0, 16)}.`;
    await page.goto('/admin/products');
    await page.locator('div.space-y-2').filter({ hasText: PRODUCT }).getByRole('button', { name: 'Edit' }).click();
    await expect(page.getByRole('heading', { name: `Edit: ${PRODUCT}` })).toBeVisible();
    await page.locator('textarea[name="description"]').fill(text);
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(page.getByText(`Saved "${PRODUCT}"`)).toBeVisible();
    expect((await ourProduct(page))!.description).toBe(text);
    expect((await ourProduct(page))!.is_active, 'still hidden').toBe(false);
  });

  test('ADM-103 Hidden product is not public', async ({ page }) => {
    const p = await ourProduct(page);
    test.skip(!p, 'Needs the E2E product (ADM-101)');
    await page.goto('/products');
    await expect(page.getByText(PRODUCT, { exact: true })).toHaveCount(0);
    const r = await page.goto(`/products/${p!.slug}`);
    expect(r?.status() === 404 || (await page.getByText(PRODUCT).count()) === 0, 'detail page hidden').toBeTruthy();
  });
});

// ---------------------------------------------------------------- SEO & Partners
test.describe('SEO & Partners', () => {
  type O = { id: number; text: string; is_active: boolean };
  const ourOffers = async (page: Page) => (await get<O[]>(page, '/content/offers')).filter((o) => o.text === OFFER);
  const offersTab = (page: Page) => page.getByRole('button', { name: 'Product offers' });

  test('ADM-110 Page loads', async ({ page }) => {
    await page.goto('/admin/website');
    await title(page, 'SEO & Partners');
    for (const t of ['Text & SEO', 'Product offers']) await expect.soft(page.getByRole('button', { name: t })).toBeVisible();
  });

  test('ADM-111 Add a test offer', async ({ page }) => {
    await page.goto('/admin/website');
    await offersTab(page).click();
    await page.getByPlaceholder('Free samples for new distributors this month').fill(OFFER);
    await page.getByRole('button', { name: 'Add', exact: true }).click();
    const row = page.locator('div').filter({ hasText: OFFER }).filter({ has: page.getByRole('button', { name: 'Delete' }) }).last();
    await expect(row).toBeVisible();
    // Live on the website as soon as it is added: switch it off at once
    if (await row.getByRole('button', { name: 'Switch off' }).isVisible()) await row.getByRole('button', { name: 'Switch off' }).click();
    await expect.poll(async () => (await ourOffers(page)).every((o) => !o.is_active)).toBeTruthy();
  });

  test('ADM-112 Delete the test offer', async ({ page }) => {
    test.skip((await ourOffers(page)).length === 0, 'Needs the E2E offer (ADM-111)');
    await page.goto('/admin/website');
    await offersTab(page).click();
    while ((await ourOffers(page)).length > 0) {
      const row = page.locator('div').filter({ hasText: OFFER }).filter({ has: page.getByRole('button', { name: 'Delete' }) }).last();
      await row.getByRole('button', { name: 'Delete' }).click();
      await expect.poll(async () => (await ourOffers(page)).length, { timeout: 15_000 }).toBeLessThan(99);
      await page.reload();
      await offersTab(page).click();
      if ((await ourOffers(page)).length > 0 && !(await row.isVisible())) break;
    }
    expect(await ourOffers(page)).toHaveLength(0);
  });

  test('ADM-113 Partner list shows', async ({ page }) => {
    await page.goto('/admin/website');
    const tab = page.getByRole('button', { name: /^partners/i });
    await expect(tab).toBeVisible();
    const answer = page.waitForResponse((r) => r.url().includes('/content/partners'));
    await tab.click();
    expect((await answer).ok()).toBeTruthy();
  });
});

// ---------------------------------------------------------------- KOKO, Reports, Alerts, Activity log, Settings
test.describe('Other admin pages', () => {
  test('ADM-120 Manage KOKO page loads', async ({ page }) => {
    await page.goto('/admin/koko');
    await title(page, 'Manage KOKO');
    await expect(page.getByRole('heading', { name: 'Facts' })).toBeVisible();
    await expect(page.getByRole('heading', { name: /^Recent chats/ })).toBeVisible();
  });

  test('ADM-130 Reports load', async ({ page }) => {
    await page.goto('/admin/analytics');
    await title(page, 'Reports');
    for (const p of ['New leads per week', 'Leads by source', 'Leads by status']) await expect.soft(page.getByRole('heading', { name: p })).toBeVisible();
  });

  test('ADM-140 Alerts load', async ({ page }) => {
    await page.goto('/admin/alerts');
    await title(page, 'Alerts');
    await expect(page.getByRole('heading', { name: 'Alerts sent' })).toBeVisible();
  });

  test('ADM-150 Activity log loads', async ({ page }) => {
    await page.goto('/admin/audit');
    await title(page, 'Activity log');
    await expect(page.locator('tbody tr').first()).toBeVisible();
    expect(await page.locator('tbody tr').count()).toBeLessThanOrEqual(200);
  });

  test('ADM-151 Test actions are logged', async ({ page }) => {
    type A = { action: string; actor_label: string; after: unknown };
    const log = await get<A[]>(page, '/admin/audit?limit=200');
    const mentions = (a: A) => JSON.stringify(a.after ?? '').includes(HOLIDAY) || a.action.startsWith('holiday.');
    const added = log.find((a) => a.action === 'holiday.added' && mentions(a));
    const removed = log.find((a) => a.action === 'holiday.removed');
    expect.soft(added, 'holiday.added in the log').toBeTruthy();
    expect.soft(removed, 'holiday.removed in the log').toBeTruthy();
    await page.goto('/admin/audit');
    await expect(page.getByRole('cell', { name: 'holiday.added' }).first()).toBeVisible();
  });

  test('ADM-160 Settings list loads', async ({ page }) => {
    await page.goto('/admin/settings');
    await title(page, 'Manage settings');
    await expect(page.getByRole('heading', { name: /^sla/ })).toBeVisible();
  });

  test('ADM-161 Search settings', async ({ page }) => {
    await page.goto('/admin/settings');
    await page.getByPlaceholder('Search, e.g. sla').fill('sla');
    const groups = page.locator('section > h2'); // the settings groups (not the hidden logout popup's heading)
    await expect(groups).not.toHaveCount(0);
    for (const h of await groups.allTextContents()) expect.soft(h).toMatch(/sla/i);
  });

  test('ADM-162 Re-read files', async ({ page }) => {
    await page.goto('/admin/settings');
    await expect(page.locator('table').first()).toBeVisible(); // wait until the settings have loaded
    const before = await page.locator('table').allTextContents();
    const answer = page.waitForResponse((r) => r.url().includes('/admin/config/reload'));
    await page.getByRole('button', { name: 'Re-read files now' }).click();
    expect((await answer).ok()).toBeTruthy();
    expect(await page.locator('table').allTextContents()).toEqual(before);
  });
});

// ---------------------------------------------------------------- Whole module
test.describe('All admin pages', () => {
  const PAGES = ['/admin/dashboard', '/admin/leads', '/admin/approvals', '/admin/users', '/admin/users/new', '/admin/team-attendance',
    '/admin/holidays', '/admin/order-boards', '/admin/auto-assign', '/admin/client-schedulers', '/admin/products', '/admin/website',
    '/admin/koko', '/admin/analytics', '/admin/alerts', '/admin/audit', '/admin/settings'];

  test('ADM-170 No errors on any admin page', async ({ page }) => {
    test.setTimeout(8 * 60_000);
    let current = '';
    const problems: string[] = [];
    // Known, logged separately: chat's live connection can't pass through Vercel (see docs/tempV.md)
    const known = (t: string) => t.includes('/api/v1/chat/ws');
    page.on('console', (m) => m.type() === 'error' && !known(m.text()) && problems.push(`${current}: ${m.text().slice(0, 160)}`));
    page.on('pageerror', (e) => problems.push(`${current}: crash ${e.message.slice(0, 160)}`));
    page.on('response', (r) => r.url().includes('/api/') && (r.status() >= 500 || r.status() === 403) && problems.push(`${current}: ${r.status()} ${new URL(r.url()).pathname}`));
    for (const p of PAGES) {
      await test.step(p, async () => {
        current = p;
        await page.goto(p);
        await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined);
        await expect.soft(page.getByText('Could not load your account'), p).toHaveCount(0);
        await expect.soft(page.getByText('Not available yet', { exact: true }), p).toHaveCount(0);
      });
    }
    expect.soft(problems, 'errors seen').toEqual([]);
  });

  test('ADM-171 Phone layout', async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: '.auth/A.json', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    await page.goto('/admin/dashboard');
    await page.getByRole('button', { name: 'Open menu' }).click();
    await expect(page.getByRole('navigation', { name: 'Portal' })).toBeVisible();
    await page.locator('#portal-sidebar').getByRole('button', { name: 'Close menu' }).click();
    await expect(page.getByText('Active staff', { exact: true })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, 'no sideways scroll').toBeLessThanOrEqual(1);
    await ctx.close();
  });

  test('ADM-172 Clean-up check', async ({ page }) => {
    const holidays = (await get<{ name: string }[]>(page, `/admin/holidays?year=${NEXT_YEAR}`)).filter((h) => h.name === HOLIDAY);
    const offers = (await get<{ text: string }[]>(page, '/content/offers')).filter((o) => o.text === OFFER);
    const sources = (await get<{ name: string }[]>(page, '/admin/harvest/sources')).filter((s) => s.name === SOURCE);
    expect.soft(holidays, 'E2E holidays left').toHaveLength(0);
    expect.soft(offers, 'E2E offers left').toHaveLength(0);
    expect.soft(sources, 'E2E sources left').toHaveLength(0);
    const product = (await get<{ name: string; is_active: boolean }[]>(page, '/admin/products')).find((p) => p.name === PRODUCT);
    expect.soft(product?.is_active ?? false, 'E2E product hidden').toBe(false);
  });
});
