// Employee module, end to end, on the live site, as tester V. One test per case in
// docs/testing/employee-e2e.xlsx (title starts with the case ID; scripts/e2e/employee_workbook.py copies
// the results in). Scope (Vineet, 12 Nov): create and KEEP test data (cleared before production);
// check-in/out included. Never changes V's password. Tests run in order; a failure doesn't stop the rest.
import { readFileSync } from 'node:fs';
import { test, expect, type Page } from '@playwright/test';
import { navFor } from '@/components/portal/SidebarNav';
import { logIn, login, type Me } from './helpers';

const STAMP = new Date().toISOString().slice(0, 16).replace('T', ' ');
const LEAD = `E2E Lead ${STAMP}`;
const TASK = `E2E Task ${STAMP}`;
const GROUP = 'E2E Group';
const me = (): Me => JSON.parse(readFileSync('../e2e-output/auth/V.me.json', 'utf8'));
const testEmployees = (): { id: number; name: string }[] => JSON.parse(readFileSync('../e2e-output/auth/stress-users.json', 'utf8'));

test.beforeEach(async ({ page }) => {
  page.on('dialog', (d) => d.accept());
});

async function get<T>(page: Page, path: string): Promise<T> {
  const r = await page.request.get(`/api/v1${path}`);
  expect(r.ok(), `GET ${path} answered ${r.status()}`).toBeTruthy();
  return r.json();
}
const note = (text: string) => test.info().annotations.push({ type: 'note', description: text });
const title = (page: Page, text: string | RegExp) => expect(page.getByRole('heading', { level: 1, name: text })).toBeVisible();

async function openSidebar(page: Page) {
  const menu = page.getByRole('button', { name: 'Open menu' });
  await expect(menu.or(page.getByRole('button', { name: 'Close menu' }).first())).toBeVisible();
  if (await menu.isVisible()) await menu.click();
}

const isoDay = (offsetDays: number) => {
  const d = new Date(Date.now() + 5.5 * 3600e3 + offsetDays * 864e5); // IST
  return d.toISOString().slice(0, 10);
};

// ---------------------------------------------------------------- Login and access
test.describe('Login & access', () => {
  test('EMP-001 Employee logs in', async ({ browser }) => {
    const c = login(test.info())!;
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await logIn(page, c.email, c.password);
    await expect(page).toHaveURL(/\/employee\/dashboard/);
    await openSidebar(page);
    await expect(page.getByText('Employee portal')).toBeVisible();
    await ctx.close();
  });

  test('EMP-002 Logged-out visitor cannot open staff pages', async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await page.goto('/employee/dashboard');
    await expect(page).toHaveURL(/\/employee\/login\?next=%2Femployee%2Fdashboard/);
    await ctx.close();
  });

  test('EMP-003 Sidebar matches the permissions', async ({ page }) => {
    await page.goto('/employee/dashboard');
    await openSidebar(page);
    const nav = page.getByRole('navigation', { name: 'Portal' });
    await expect(nav.locator('a').first()).toBeVisible();
    const shown = new Set<string>();
    const heads = nav.locator('button[aria-controls^="nav-"]');
    const n = await heads.count();
    if (n === 0) (await nav.locator('a').evaluateAll((as) => as.map((a) => a.getAttribute('href')!))).forEach((h) => shown.add(h));
    for (let i = 0; i < n; i++) {
      const head = heads.nth(i);
      if ((await head.getAttribute('aria-expanded')) !== 'true') await head.click();
      const list = nav.locator(`#${await head.getAttribute('aria-controls')}`);
      (await list.locator('a').evaluateAll((as) => as.map((a) => a.getAttribute('href')!))).forEach((h) => shown.add(h));
    }
    const m = me();
    const expected = navFor({ permissions: m.permissions, modules: m.modules }).flatMap((g) => g.items.map((i) => i.href)).sort();
    expect([...shown].sort()).toEqual(expected);
    note(`${expected.length} pages for permissions: ${m.permissions.join(', ')}.`);
  });

  test('EMP-004 Admin API refused', async ({ page }) => {
    test.skip(me().permissions.includes('staff.approve'), 'V has staff.approve now');
    expect((await page.request.get('/api/v1/admin/users')).status()).toBe(403);
  });

  test('EMP-005 Admin page shows no staff data', async ({ page }) => {
    test.skip(me().permissions.includes('staff.approve'), 'V has staff.approve now');
    const refused = page.waitForResponse((r) => r.url().includes('/api/v1/admin/users'));
    await page.goto('/admin/users');
    expect((await refused).status()).toBe(403);
    await expect(page.getByRole('cell', { name: /@kjs-e2e\.test/ })).toHaveCount(0);
  });

  test('EMP-006 Logout ends the session', async ({ browser }) => {
    const c = login(test.info())!;
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await logIn(page, c.email, c.password);
    await openSidebar(page);
    await page.locator('#portal-sidebar').getByRole('button', { name: 'Log out' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Log out' }).click();
    await expect(page.getByText("You've logged out safely")).toBeVisible();
    expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);
    await ctx.close();
  });
});

// ---------------------------------------------------------------- Today
test.describe('Today', () => {
  test('EMP-010 Today loads', async ({ page }) => {
    await page.goto('/employee/dashboard');
    await title(page, new RegExp(`^Good (morning|afternoon|evening), ${me().name.split(' ')[0]}`));
    await expect(page.getByRole('heading', { name: 'My leads' })).toBeVisible();
  });

  test('EMP-011 Task counts match the server', async ({ page }) => {
    const s = await get<{ total: number; done: number; pending: number; overdue: number }>(page, '/tasks/stats');
    await page.goto('/employee/dashboard');
    for (const [label, v] of [['Tasks', s.total], ['Done', s.done], ['Pending', s.pending], ['Overdue', s.overdue]] as const) {
      await expect.soft(page.locator('a.card').filter({ hasText: new RegExp(`^${label}`) }), label).toContainText(String(v));
    }
  });
});

// ---------------------------------------------------------------- My attendance
test.describe('My attendance', () => {
  type Today = { check_in: string | null; check_out: string | null; is_checked_in?: boolean };
  const punch = (page: Page) => page.getByRole('button', { name: /Check-(in|out)/ }).first();
  // The punch button ignores clicks until today's attendance has loaded: open the page and wait for it
  async function openAttendance(page: Page) {
    const loaded = page.waitForResponse((r) => r.url().includes('/api/v1/attendance/today') && r.ok());
    await page.goto('/employee/attendance');
    await loaded;
    await expect(punch(page)).toBeVisible();
  }

  test('EMP-020 Attendance page loads', async ({ page }) => {
    await page.goto('/employee/attendance');
    await expect(punch(page)).toBeVisible();
    await expect(page.getByTitle('List View')).toBeVisible();
  });

  test('EMP-021 Check in', async ({ page }) => {
    await openAttendance(page);
    if (/Check-out/.test((await punch(page).textContent()) ?? '')) note('V was already checked in.');
    else {
      await punch(page).click();
      await expect(page.getByRole('button', { name: /Check-out/ })).toBeVisible();
    }
    expect((await get<Today>(page, '/attendance/today')).check_in).toBeTruthy();
  });

  test('EMP-022 Check out with a note', async ({ page }) => {
    await openAttendance(page);
    await expect(page.getByRole('button', { name: /Check-out/ })).toBeVisible();
    await page.getByPlaceholder('Add notes for check-out').fill('E2E check-out');
    await page.getByRole('button', { name: /Check-out/ }).click();
    await expect(page.getByRole('button', { name: /Check-in again/ })).toBeVisible();
    expect((await get<Today>(page, '/attendance/today')).check_out).toBeTruthy();
  });

  test('EMP-023 Switch views', async ({ page }) => {
    await page.goto('/employee/attendance');
    for (const v of ['Tabular View', 'Overtime View']) {
      await page.getByTitle('Views').click();
      await page.getByRole('menuitem', { name: v }).click();
      await expect.soft(page.getByText('Could not load', { exact: false }), v).toHaveCount(0);
    }
    await page.getByTitle('Calendar View').click();
    await page.getByTitle('List View').click();
    await expect(page.getByText('Total Hours').first()).toBeVisible();
  });

  test('EMP-024 Apply for leave', async ({ page }) => {
    await page.goto('/employee/attendance');
    await page.getByRole('button', { name: /^Leave Applications/ }).click();
    await page.getByRole('button', { name: '+ Apply Leave' }).first().click();
    const form = page.locator('form').filter({ has: page.locator('select[name="leave_type"]') });
    await form.locator('select[name="leave_type"]').selectOption('casual');
    const taken = (await get<{ start_date: string; end_date: string; status: string }[]>(page, '/attendance/leaves'))
      .filter((l) => l.status !== 'rejected' && l.status !== 'cancelled');
    let off = 30;
    while (taken.some((l) => !(isoDay(off + 1) < l.start_date || isoDay(off) > l.end_date))) off += 3;
    await form.locator('input[name="start_date"]').fill(isoDay(off));
    await form.locator('input[name="end_date"]').fill(isoDay(off + 1));
    note(`Leave ${isoDay(off)} to ${isoDay(off + 1)}.`);
    await form.locator('[name="reason"]').fill(`E2E test leave ${STAMP}`);
    await form.getByRole('button', { name: 'Submit Application' }).click();
    await expect.poll(async () => (await get<{ reason: string; status: string }[]>(page, '/attendance/leaves'))
      .some((l) => l.reason === `E2E test leave ${STAMP}`)).toBeTruthy();
    await expect(page.getByText('Casual Leave').first()).toBeVisible();
  });

  test('EMP-025 Leave ending before it starts is refused', async ({ page }) => {
    const before = (await get<unknown[]>(page, '/attendance/leaves')).length;
    await page.goto('/employee/attendance');
    await page.getByRole('button', { name: /^Leave Applications/ }).click();
    await page.getByRole('button', { name: '+ Apply Leave' }).first().click();
    const form = page.locator('form').filter({ has: page.locator('select[name="leave_type"]') });
    await form.locator('input[name="start_date"]').fill(isoDay(40));
    await form.locator('input[name="end_date"]').fill(isoDay(38));
    await form.locator('[name="reason"]').fill('E2E wrong dates');
    await form.getByRole('button', { name: 'Submit Application' }).click();
    await page.waitForTimeout(2000);
    expect((await get<unknown[]>(page, '/attendance/leaves')).length, 'no leave saved').toBe(before);
  });

  test('EMP-026 Missed-punch request', async ({ page }) => {
    await page.goto('/employee/attendance');
    await page.getByRole('button', { name: /^Regularization/ }).click();
    await page.getByRole('button', { name: '+ New Request' }).click();
    const form = page.locator('form').filter({ has: page.getByRole('button', { name: 'Send Fix Request' }) });
    const used = JSON.stringify(await get<unknown>(page, '/attendance/regularizations'));
    let back = -1;
    while (used.includes(`"${isoDay(back)}"`) || new Date(isoDay(back)).getUTCDay() === 0) back--;
    await form.locator('input[name="day"]').fill(isoDay(back));
    note(`Missed punch for ${isoDay(back)}.`);
    await form.locator('input[name="check_in"]').fill('09:30');
    await form.locator('input[name="check_out"]').fill('18:30');
    await form.locator('[name="reason"]').fill(`E2E missed punch ${STAMP}`);
    await form.getByRole('button', { name: 'Send Fix Request' }).click();
    await expect.poll(async () => JSON.stringify(await get<unknown>(page, '/attendance/regularizations')).includes(`E2E missed punch ${STAMP}`),
      { timeout: 20_000 }).toBeTruthy();
  });

  test('EMP-027 Reports and shifts', async ({ page }) => {
    await page.goto('/employee/attendance');
    await page.getByRole('button', { name: 'Reports', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'My Attendance Reports' })).toBeVisible();
    await page.getByRole('button', { name: 'Shift Schedule', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Company Shifts' })).toBeVisible();
  });

  test('EMP-028 Requests reach the admin', async ({ playwright, baseURL }) => {
    const ctx = await playwright.request.newContext({ baseURL, storageState: '../e2e-output/auth/A.json' });
    const r = await ctx.get('/api/v1/admin/approvals');
    expect(r.ok(), 'admin session (run project A setup first)').toBeTruthy();
    const text = JSON.stringify(await r.json());
    expect.soft(text, 'missed punch in Approvals').toContain(`E2E missed punch ${STAMP}`);
    const leaves = await ctx.get('/api/v1/attendance/leaves/approvals');
    expect.soft(JSON.stringify(await leaves.json()), 'leave in leave approvals').toContain(`E2E test leave ${STAMP}`);
    await ctx.dispose();
  });
});

// ---------------------------------------------------------------- Leads
test.describe('Leads', () => {
  test('EMP-040 Leads list loads', async ({ page }) => {
    await page.goto('/employee/contacts');
    await title(page, 'Leads');
    await expect(page.getByText(/Showing \d+ to \d+ of \d+|No /).first()).toBeVisible();
  });

  test('EMP-041 Search leads', async ({ page }) => {
    await page.goto('/employee/contacts');
    await expect(page.getByText(/Showing \d+ to \d+ of \d+|No /).first()).toBeVisible(); // wait for the list
    const first = page.locator('tbody tr').first().locator('a').first();
    test.skip(!(await first.isVisible()), 'No leads to search');
    const name = (await first.textContent())!.trim();
    await page.getByPlaceholder('Search').fill(name);
    await expect(page.getByRole('link', { name }).first()).toBeVisible();
    await page.getByPlaceholder('Search').fill('zz-no-such-lead-zz');
    await expect(page.getByText('Nothing matches your search')).toBeVisible();
  });

  test('EMP-042 Add an internal lead', async ({ page }) => {
    await page.goto('/employee/internal-leads');
    await page.getByRole('button', { name: '+ Add lead' }).click();
    await page.locator('#il-name').fill(LEAD);
    await page.locator('#il-company').fill('E2E Co');
    await page.locator('#il-phone').fill('9876512345');
    await page.locator('#il-email').fill('e2e.lead@kjs-e2e.test');
    await page.locator('#il-country').fill('India');
    const cat = page.locator('#il-cat');
    if ((await cat.locator('option').count()) > 1) await cat.selectOption({ index: 1 });
    await page.locator('#il-qty').fill('1 tonne a month');
    await page.locator('#il-msg').fill('E2E test lead: wants samples of instant coffee.');
    await page.getByRole('button', { name: 'Save lead' }).click();
    // Saving opens the new lead's page
    await expect(page.getByRole('heading', { level: 1, name: LEAD })).toBeVisible({ timeout: 30_000 });
    await page.goto('/employee/internal-leads');
    await expect(page.getByRole('link', { name: LEAD }).first()).toBeVisible();
  });

  test('EMP-043 Lead without phone refused', async ({ page }) => {
    await page.goto('/employee/internal-leads');
    await page.getByRole('button', { name: '+ Add lead' }).click();
    await page.locator('#il-name').fill('E2E No Phone');
    const saved = page.waitForResponse((r) => r.url().includes('/api/v1/employee/leads') && r.request().method() === 'POST', { timeout: 8000 }).catch(() => null);
    await page.getByRole('button', { name: 'Save lead' }).click();
    const r = await saved;
    expect(r === null || !r.ok(), 'not saved').toBeTruthy();
    await expect(page.getByRole('link', { name: 'E2E No Phone' })).toHaveCount(0);
  });

  test('EMP-044 New lead shows in Leads', async ({ page }) => {
    await page.goto('/employee/contacts');
    await page.getByPlaceholder('Search').fill(LEAD);
    await expect(page.getByRole('link', { name: LEAD }).first()).toBeVisible();
  });

  async function openLead(page: Page) {
    await page.goto('/employee/internal-leads');
    await page.getByRole('link', { name: LEAD }).first().click();
    await expect(page.getByRole('heading', { name: 'Lead Pipeline' })).toBeVisible();
  }

  test('EMP-045 Open the lead', async ({ page }) => {
    await openLead(page);
    await expect(page.getByRole('heading', { name: 'Quick actions' })).toBeVisible();
  });

  test('EMP-046 Add a note', async ({ page }) => {
    await openLead(page);
    const text = `E2E note: called, wants samples (${STAMP})`;
    await page.getByRole('tab', { name: 'Notes' }).click();
    await page.getByPlaceholder('What happened? e.g. Called, wants samples of 3-in-1').fill(text);
    await page.getByRole('button', { name: 'Add note' }).click();
    await expect(page.getByText(text)).toBeVisible();
  });

  test('EMP-047 Add a task from the lead', async ({ page }) => {
    await openLead(page);
    const text = `E2E follow-up ${STAMP}`;
    await page.getByRole('tab', { name: 'Task' }).click();
    await page.getByPlaceholder('e.g. Send the price sheet').fill(text);
    await page.getByRole('button', { name: 'Add task' }).click();
    await expect.poll(async () => (await get<{ title: string }[]>(page, '/tasks')).some((t) => t.title === text), { timeout: 20_000 }).toBeTruthy();
    await page.goto('/employee/tasks');
    await expect(page.getByText(text)).toBeVisible();
  });

  test('EMP-048 Koko leads page loads', async ({ page }) => {
    await page.goto('/employee/koko-leads');
    await title(page, 'Koko chat leads');
  });
});

// ---------------------------------------------------------------- Tasks & Track
test.describe('Tasks & Track', () => {
  type T = { id: number; title: string; status: string; outcome: string | null; assignee_id: number };
  const mine = async (page: Page) => (await get<T[]>(page, '/tasks')).find((t) => t.title === TASK);
  const row = (page: Page) => page.locator('div.card').filter({ hasText: TASK }).first();

  test('EMP-050 Tasks page loads', async ({ page }) => {
    await page.goto('/employee/tasks');
    await title(page, 'Tasks & Track');
    await expect(page.getByPlaceholder('Send spec sheet to Al Noor')).toBeVisible();
  });

  test('EMP-051 Add a task for me', async ({ page }) => {
    await page.goto('/employee/tasks');
    await page.getByPlaceholder('Send spec sheet to Al Noor').fill(TASK);
    await page.locator('input[name="notes"]').fill('E2E test task');
    await page.getByRole('button', { name: 'Add task' }).click();
    await expect(row(page)).toBeVisible();
    expect((await mine(page))?.status).toBe('todo');
  });

  test('EMP-052 Start the task', async ({ page }) => {
    test.skip(!(await mine(page)), 'Needs EMP-051');
    await page.goto('/employee/tasks');
    await row(page).getByRole('button', { name: 'Details' }).click();
    await row(page).getByRole('button', { name: 'Start' }).click();
    await expect.poll(async () => (await mine(page))?.status).toBe('doing');
  });

  test('EMP-053 Save an outcome', async ({ page }) => {
    test.skip(!(await mine(page)), 'Needs EMP-051');
    await page.goto('/employee/tasks');
    await row(page).getByRole('button', { name: 'Details' }).click();
    await row(page).getByPlaceholder('What came of it?').fill('E2E outcome: sent the catalogue');
    await row(page).getByRole('button', { name: 'Save' }).click();
    await expect.poll(async () => (await mine(page))?.outcome).toBe('E2E outcome: sent the catalogue');
  });

  test('EMP-054 Finish the task', async ({ page }) => {
    test.skip(!(await mine(page)), 'Needs EMP-051');
    await page.goto('/employee/tasks');
    await row(page).getByRole('checkbox', { name: 'Done' }).click(); // the tick follows the server's answer
    await expect.poll(async () => (await mine(page))?.status).toBe('done');
    await page.locator('select').filter({ has: page.locator('option[value="doing"]') }).selectOption('done');
    await expect(row(page)).toBeVisible();
  });

  test('EMP-055 Give a task to a colleague', async ({ page }) => {
    test.skip(!me().permissions.includes('tasks.assign'), 'V has no tasks.assign');
    const who = testEmployees()[0];
    const text = `E2E delegated task ${STAMP}`;
    await page.goto('/employee/tasks');
    await page.getByPlaceholder('Send spec sheet to Al Noor').fill(text);
    await page.locator('select[name="assignee_id"]').selectOption({ label: who.name });
    await page.getByRole('button', { name: 'Add task' }).click();
    await expect.poll(async () => (await get<T[]>(page, `/tasks?assignee_id=${who.id}`)).some((t) => t.title === text), { timeout: 20_000 }).toBeTruthy();
    note(`Given to ${who.name}.`);
  });

  test('EMP-056 Task without a title refused', async ({ page }) => {
    await page.goto('/employee/tasks');
    await page.getByRole('button', { name: 'Add task' }).click();
    await expect(page.getByPlaceholder('Send spec sheet to Al Noor')).toHaveJSProperty('validity.valueMissing', true);
  });
});

// ---------------------------------------------------------------- Batches, boards
test.describe('Batches and boards', () => {
  test('EMP-060 Batches page loads', async ({ page }) => {
    await page.goto('/employee/batches');
    await title(page, 'My batches');
  });

  test('EMP-065 Boards page loads', async ({ page }) => {
    await page.goto('/employee/order-boards');
    await title(page, 'My order boards');
  });
});

// ---------------------------------------------------------------- Chat
test.describe('Chat', () => {
  type Ch = { id: number; title?: string; name?: string; kind: string };
  const group = async (page: Page) => (await get<Ch[]>(page, '/chat/channels')).find((c) => c.kind === 'group' && (c.name === GROUP || c.title === GROUP));

  async function openGroup(page: Page) {
    await page.goto('/employee/chat');
    await page.getByRole('button', { name: new RegExp(GROUP) }).first().click();
    await expect(page.getByRole('textbox', { name: 'Message' })).toBeVisible();
  }

  test('EMP-070 Chat page loads', async ({ page }) => {
    await page.goto('/employee/chat');
    await expect(page.getByRole('button', { name: 'New chat or channel' })).toBeVisible();
  });

  test('EMP-071 Start a group chat', async ({ page }) => {
    if (await group(page)) return note('E2E Group existed from an earlier run; reused.');
    const [a, b] = testEmployees();
    await page.goto('/employee/chat');
    await page.getByRole('button', { name: 'New chat or channel' }).click();
    const dlg = page.getByRole('dialog', { name: 'New chat' });
    await dlg.getByRole('tab', { name: 'Group chat' }).click();
    await dlg.getByPlaceholder('Group name (optional)').fill(GROUP);
    for (const p of [a, b]) {
      await dlg.getByLabel('Find a colleague').fill(p.name);
      await dlg.getByRole('checkbox', { name: p.name }).check();
    }
    await dlg.getByRole('button', { name: 'Start group chat' }).click();
    await expect(page.getByRole('textbox', { name: 'Message' })).toBeVisible();
    expect(await group(page)).toBeTruthy();
  });

  test('EMP-072 Send a message', async ({ page }) => {
    test.skip(!(await group(page)), 'Needs EMP-071');
    await openGroup(page);
    const text = `E2E hello ${STAMP}`;
    await page.getByRole('textbox', { name: 'Message' }).fill(text);
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(page.getByText(text)).toBeVisible();
  });

  test('EMP-073 Edit own message', async ({ page }) => {
    test.skip(!(await group(page)), 'Needs EMP-071');
    await openGroup(page);
    const msg = page.locator('div.group').filter({ hasText: `E2E hello ${STAMP}` }).last();
    await msg.hover();
    await msg.getByRole('button', { name: 'Edit' }).click();
    await page.getByRole('textbox', { name: 'Edit message' }).fill(`E2E hello ${STAMP} (edited by test)`);
    await page.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText(`E2E hello ${STAMP} (edited by test)`)).toBeVisible();
    await expect(msg.getByText('(edited)')).toBeVisible();
  });

  test('EMP-074 Delete own message', async ({ page }) => {
    test.skip(!(await group(page)), 'Needs EMP-071');
    await openGroup(page);
    const text = `E2E to delete ${STAMP}`;
    await page.getByRole('textbox', { name: 'Message' }).fill(text);
    await page.getByRole('button', { name: 'Send' }).click();
    const msg = page.locator('div.group').filter({ hasText: text }).last();
    await expect(msg).toBeVisible();
    await msg.hover();
    await msg.getByRole('button', { name: 'Delete' }).click();
    await msg.getByRole('button', { name: 'Yes' }).click();
    await expect(page.getByText(text)).toHaveCount(0);
    await expect(page.getByText('Message deleted').last()).toBeVisible();
  });

  test('EMP-075 Live connection', async ({ page }) => {
    const ws = page.waitForEvent('websocket', { timeout: 20_000 });
    await page.goto('/employee/chat');
    const socket = await ws;
    const opened = await Promise.race([
      socket.waitForEvent('framereceived', { timeout: 15_000 }).then(() => true),
      socket.waitForEvent('close', { timeout: 15_000 }).then(() => false),
    ]).catch(() => false);
    expect(opened, `live connection to ${socket.url()} (known: 404 on Vercel)`).toBeTruthy();
  });
});

// ---------------------------------------------------------------- Profile
test.describe('Profile', () => {
  const pwForm = (page: Page) => page.locator('form').filter({ has: page.getByRole('button', { name: 'Change password' }) });

  test('EMP-080 Profile loads', async ({ page }) => {
    await page.goto('/employee/me');
    await title(page, 'Profile');
    await expect(page.locator('input[name="name"]')).toHaveValue(me().name);
  });

  test('EMP-081 Save a setting', async ({ page }) => {
    await page.goto('/employee/me');
    const box = page.locator('input[name="notify_whatsapp"]');
    const was = await box.isChecked();
    await box.setChecked(!was);
    await page.locator('form').filter({ has: box }).getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('Saved.')).toBeVisible();
    await page.reload();
    await expect(page.locator('input[name="notify_whatsapp"]')).toBeChecked({ checked: !was });
    note(`WhatsApp setting now ${!was ? 'on' : 'off'} (kept).`);
  });

  test('EMP-082 Wrong current password refused', async ({ page }) => {
    await page.goto('/employee/me');
    const f = pwForm(page);
    await f.locator('input[name="current"]').fill('wrong-current-e2e');
    await f.locator('input[name="new"]').fill('E2E-not-used-123');
    await f.locator('input[name="repeat"]').fill('E2E-not-used-123');
    const answer = page.waitForResponse((r) => r.url().includes('/api/v1/auth/password'));
    await f.getByRole('button', { name: 'Change password' }).click();
    expect((await answer).ok(), 'refused').toBeFalsy();
    // V's real password still works
    const c = login(test.info())!;
    const check = await page.request.post('/api/v1/auth/login', { data: { email: c.email, password: c.password }, headers: { 'x-requested-with': 'kjs' } });
    expect(check.ok(), 'old password still valid').toBeTruthy();
  });

  test('EMP-083 New passwords must match', async ({ page }) => {
    await page.goto('/employee/me');
    const f = pwForm(page);
    let sent = false;
    page.on('request', (r) => r.url().includes('/api/v1/auth/password') && (sent = true));
    await f.locator('input[name="current"]').fill('anything');
    await f.locator('input[name="new"]').fill('E2E-first-12345');
    await f.locator('input[name="repeat"]').fill('E2E-second-1234');
    await f.getByRole('button', { name: 'Change password' }).click();
    await page.waitForTimeout(1500);
    expect(sent, 'nothing sent').toBeFalsy();
  });

  test('EMP-084 Short new password refused', async ({ page }) => {
    await page.goto('/employee/me');
    const f = pwForm(page);
    await f.locator('input[name="current"]').fill('anything');
    await f.locator('input[name="new"]').fill('short');
    await f.locator('input[name="repeat"]').fill('short');
    await f.getByRole('button', { name: 'Change password' }).click();
    await expect(f.locator('input[name="new"]')).toHaveJSProperty('validity.tooShort', true);
  });
});

// ---------------------------------------------------------------- Whole module
test.describe('All employee pages', () => {
  test('EMP-090 No errors on any page', async ({ page }) => {
    test.setTimeout(6 * 60_000);
    const m = me();
    const pages = navFor({ permissions: m.permissions, modules: m.modules }).flatMap((g) => g.items.map((i) => i.href)).filter((h) => h.startsWith('/employee'));
    let current = '';
    const problems: string[] = [];
    const known = (t: string) => t.includes('/api/v1/chat/ws'); // EMP-075
    page.on('console', (msg) => msg.type() === 'error' && !known(msg.text()) && problems.push(`${current}: ${msg.text().slice(0, 160)}`));
    page.on('pageerror', (e) => problems.push(`${current}: crash ${e.message.slice(0, 160)}`));
    page.on('response', (r) => r.url().includes('/api/') && (r.status() >= 500 || r.status() === 403) && problems.push(`${current}: ${r.status()} ${new URL(r.url()).pathname}`));
    for (const p of pages) {
      await test.step(p, async () => {
        current = p;
        await page.goto(p);
        await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined);
        await expect.soft(page.getByText('Could not load your account'), p).toHaveCount(0);
        await expect.soft(page.getByText('Not available yet', { exact: true }), p).toHaveCount(0);
      });
    }
    expect.soft(problems, 'errors seen').toEqual([]);
    note(`${pages.length} pages checked.`);
  });

  test('EMP-091 Phone layout', async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: '../e2e-output/auth/V.json', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    await page.goto('/employee/dashboard');
    await page.getByRole('button', { name: 'Open menu' }).click();
    await expect(page.getByRole('navigation', { name: 'Portal' })).toBeVisible();
    await page.locator('#portal-sidebar').getByRole('button', { name: 'Close menu' }).click();
    await expect(page.getByRole('heading', { name: 'My leads' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), 'no sideways scroll').toBeLessThanOrEqual(1);
    await ctx.close();
  });
});
