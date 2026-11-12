// Shared helpers for the live-site tests (see TEST-CASES.md).
import { expect, type APIRequestContext, type Page, type Response } from '@playwright/test';
import path from 'node:path';

/** Where the logged-in session is saved (git-ignored). */
export const STORAGE = path.resolve(__dirname, '../.auth/user.json');

export type Me = {
  id: number;
  name: string;
  email: string;
  role: string;
  permissions: string[];
  modules?: Record<string, boolean>;
};

// ----- Which sidebar links an account may see -----
// A copy of the NAV rules in src/components/portal/SidebarNav.tsx and AREA_PAGES in src/lib/modules.ts.
// A copy on purpose: the test checks the app against what we expect, not against itself.
// If the sidebar changes, update this list too.
type Perm = string | string[] | null;
export const NAV: { href: string; label: string; perm: Perm }[] = [
  { href: '/employee/dashboard', label: 'Today', perm: null },
  { href: '/employee/chat', label: 'Chat', perm: null },
  { href: '/employee/attendance', label: 'My attendance', perm: null },
  { href: '/employee/batches', label: 'My batches', perm: null },
  { href: '/employee/order-boards', label: 'My order boards', perm: null },
  { href: '/employee/me', label: 'Profile', perm: null },
  { href: '/employee/contacts', label: 'Leads', perm: 'leads.view' },
  { href: '/admin/leads', label: 'All Enquiries', perm: 'leads.view_all' },
  { href: '/employee/tasks', label: 'Tasks & Track', perm: null },
  { href: '/employee/koko-leads', label: 'Koko chat leads', perm: 'leads.view' },
  { href: '/employee/internal-leads', label: 'Internal leads', perm: 'leads.view' },
  { href: '/admin/dashboard', label: 'Admin overview', perm: 'staff.approve' },
  { href: '/admin/approvals', label: 'All approvals', perm: ['staff.approve', 'attendance.manage', 'files.approve'] },
  { href: '/admin/users', label: 'Manage employees', perm: 'staff.approve' },
  { href: '/admin/team-attendance', label: 'Attendance', perm: 'attendance.manage' },
  { href: '/admin/holidays', label: 'Holidays', perm: 'calendar.edit' },
  { href: '/admin/order-boards', label: 'All order boards', perm: 'boards.manage' },
  { href: '/admin/auto-assign', label: 'Lead auto-assign', perm: 'assign.manage' },
  { href: '/admin/client-schedulers', label: 'Client Schedulers', perm: 'assign.manage' },
  { href: '/admin/products', label: 'All Products', perm: 'catalog.edit' },
  { href: '/admin/website', label: 'SEO & Partners', perm: ['content.edit', 'leads.view_all'] },
  { href: '/admin/koko', label: 'Manage KOKO', perm: 'content.edit' },
  { href: '/admin/analytics', label: 'Reports', perm: 'staff.approve' },
  { href: '/admin/alerts', label: 'Alerts', perm: 'staff.approve' },
  { href: '/admin/audit', label: 'Activity log', perm: 'audit.view' },
  { href: '/admin/settings', label: 'Manage settings', perm: 'staff.approve' },
];

const AREA_PAGES: Record<string, string[]> = {
  batches: ['/employee/batches', '/admin/auto-assign'],
  order_boards: ['/employee/order-boards', '/admin/order-boards'],
  attendance: ['/employee/attendance', '/admin/team-attendance', '/admin/holidays'],
  website_admin: ['/admin/products', '/admin/website', '/admin/koko'],
  analytics: ['/admin/analytics'],
  alerts: ['/admin/alerts'],
  audit: ['/admin/audit'],
  chat: ['/employee/chat'],
  lead_harvester: ['/admin/client-schedulers'],
};

const hasPerm = (perm: Perm, mine: string[]) =>
  perm === null || (Array.isArray(perm) ? perm.some((p) => mine.includes(p)) : mine.includes(perm));

/** The area is switched off for this person (then the link is hidden, but that is not a permission refusal). */
export function moduleOff(me: Me, href: string) {
  const area = Object.entries(AREA_PAGES).find(([, pages]) => pages.some((p) => href === p || href.startsWith(`${p}/`)))?.[0];
  return !!area && me.modules?.[area] === false;
}

/** Links this account must see, and links it must not have (by permission). */
export function expectedNav(me: Me) {
  const allowed = NAV.filter((n) => hasPerm(n.perm, me.permissions) && !moduleOff(me, n.href));
  const refused = NAV.filter((n) => !hasPerm(n.perm, me.permissions));
  return { allowed, refused };
}

/** "Who am I" from the API, using the saved session. */
export async function getMe(request: APIRequestContext): Promise<Me> {
  const res = await request.get('/api/v1/auth/me');
  expect(res.status(), 'GET /api/v1/auth/me').toBe(200);
  return res.json();
}

// ----- Watching a page for problems -----

/** Starts recording console errors, page crashes and bad API answers on this page. */
export function watch(page: Page) {
  const consoleErrors: string[] = [];
  const crashes: string[] = [];
  const badApi: string[] = [];
  const forbidden: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });
  page.on('pageerror', (e) => crashes.push(e.message));
  page.on('response', (r: Response) => {
    const url = new URL(r.url());
    if (!url.pathname.startsWith('/api/')) return;
    const s = r.status();
    const line = `${s} ${r.request().method()} ${url.pathname}`;
    if (s === 403) forbidden.push(line);
    if (s === 401 || s === 403 || s >= 500) badApi.push(line);
  });
  return { consoleErrors, crashes, badApi, forbidden };
}

/** Waits until the portal frame and the page's own data have loaded (no "Loading…" left). */
export async function settle(page: Page) {
  await expect(page.getByRole('button', { name: /^(Open|Close) menu$/ })).toBeVisible({ timeout: 60_000 });
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined); // chat/polling may never idle
  await expect(page.getByText('Loading…')).toHaveCount(0, { timeout: 30_000 });
}

/** Opens the sidebar (if closed) and returns every link in it, opening each group in turn. */
export async function sidebarLinks(page: Page): Promise<string[]> {
  const menu = page.getByRole('button', { name: 'Open menu' });
  if (await menu.isVisible()) await menu.click();
  const nav = page.getByRole('navigation', { name: 'Portal' });
  await expect(nav).toBeVisible();
  const hrefs = new Set<string>();
  const read = async () => {
    for (const h of await nav.locator('a[href]').evaluateAll((as) => as.map((a) => a.getAttribute('href') || ''))) hrefs.add(h);
  };
  await read();
  const groups = nav.locator('button[aria-expanded]');
  const n = await groups.count();
  for (let i = 0; i < n; i++) {
    const g = groups.nth(i);
    if ((await g.getAttribute('aria-expanded')) !== 'true') await g.click();
    await read();
  }
  return [...hrefs].map((h) => h.replace(/^\/en(?=\/)/, '').split(/[?#]/)[0]);
}

/** Logs in through the real login form. Used only twice per run (setup + logout test): no retry loops. */
export async function loginUI(page: Page, email: string, password: string) {
  await page.goto('/employee/login');
  await page.getByLabel('Work email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.locator('form').getByRole('button', { name: 'Log in' }).click();
}

/** The API path that needs each permission (a read-only GET), for TC12. */
export const PERM_API: Record<string, string> = {
  'staff.approve': '/api/v1/admin/stats',
  'catalog.edit': '/api/v1/admin/products',
  'leads.view_all': '/api/v1/admin/sla',
  'audit.view': '/api/v1/admin/audit',
  'assign.manage': '/api/v1/assign/overview',
};

/** The error screens the portal can show. */
export const ERROR_SCREENS = /Could not load|Not available yet|Something went wrong|Application error/i;
