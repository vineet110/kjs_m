// TC08 - TC10: the sidebar shows the right links, and every allowed page opens cleanly (see TEST-CASES.md).
import { expect, test, type Page } from '@playwright/test';
import { ERROR_SCREENS, expectedNav, getMe, NAV, settle, sidebarLinks, watch } from './helpers';

/** Opens a page and checks it for error screens, crashes, bad API answers and console errors. */
async function openClean(page: Page, href: string) {
  const w = watch(page);
  await page.goto(href);
  await settle(page);
  expect(new URL(page.url()).pathname, 'stayed on the page (not sent away)').toBe(href);
  await expect(page.getByText(ERROR_SCREENS), 'error screen').toHaveCount(0);
  expect(w.crashes, 'page crashes').toEqual([]);
  expect(w.badApi, 'API answers 401/403/5xx').toEqual([]);
  expect(w.consoleErrors, 'console errors').toEqual([]);
}

test('TC08 sidebar shows exactly the allowed links', async ({ page, request }) => {
  const me = await getMe(request);
  const { allowed, refused } = expectedNav(me);
  await page.goto('/employee/dashboard');
  await settle(page);
  const shown = await sidebarLinks(page);
  for (const n of allowed) expect.soft(shown, `missing link: ${n.label} (${n.href})`).toContain(n.href);
  for (const n of refused) expect.soft(shown, `link shown without permission: ${n.label} (${n.href})`).not.toContain(n.href);
});

// One test per sidebar page, so the report lists each page on its own line. Pages the account may not
// open are skipped here (TC11 tests them).
for (const n of NAV) {
  test(`TC09 page opens: ${n.label} (${n.href})`, async ({ page, request }) => {
    const me = await getMe(request);
    test.skip(!expectedNav(me).allowed.some((a) => a.href === n.href), 'not allowed for this account (see TC11)');
    await openClean(page, n.href);
  });
}

// Detail pages: open the first item of a list, if there is one
const DETAILS = [
  { list: '/employee/contacts', prefix: '/employee/contacts/', perm: 'leads.view' },
  { list: '/employee/order-boards', prefix: '/employee/order-boards/', perm: null },
  { list: '/admin/order-boards', prefix: '/admin/order-boards/', perm: 'boards.manage' },
  { list: '/admin/users', prefix: '/admin/users/', perm: 'staff.approve' },
];
for (const d of DETAILS) {
  test(`TC10 detail page opens: first item of ${d.list}`, async ({ page, request }) => {
    const me = await getMe(request);
    test.skip(!!d.perm && !me.permissions.includes(d.perm), `needs ${d.perm}`);
    await page.goto(d.list);
    await settle(page);
    const hrefs = await page
      .locator(`main a[href^="${d.prefix}"], a[href^="${d.prefix}"]`)
      .evaluateAll((as) => as.map((a) => a.getAttribute('href') || ''));
    const first = hrefs.find((h) => !h.endsWith('/new'));
    test.skip(!first, 'the list is empty');
    await openClean(page, first!.split(/[?#]/)[0]);
  });
}
