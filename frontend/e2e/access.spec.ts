// TC11 + TC12: pages and API calls the account has no permission for are refused (see TEST-CASES.md).
import { expect, test } from '@playwright/test';
import { expectedNav, getMe, moduleOff, NAV, PERM_API, settle, watch } from './helpers';

// TC11: one test per portal page, skipped when the account may open it (TC09 covers those)
for (const n of NAV) {
  test(`TC11 refused without permission: ${n.label} (${n.href})`, async ({ page, request }, info) => {
    const me = await getMe(request);
    test.skip(!expectedNav(me).refused.some((r) => r.href === n.href), 'allowed for this account (see TC09)');
    test.skip(moduleOff(me, n.href), 'area switched off for this account');

    const w = watch(page);
    await page.goto(n.href);
    await settle(page).catch(() => undefined); // a redirect may land anywhere

    const sentAway = new URL(page.url()).pathname !== n.href;
    const saysNo = (await page.getByText(/don.t have permission|not allowed|Not available yet/i).count()) > 0;
    const api403 = w.forbidden.length > 0;
    info.annotations.push({ type: 'result', description: `sent away: ${sentAway}, says no: ${saysNo}, API 403: ${w.forbidden.join('; ') || 'none'}` });
    expect(sentAway || saysNo || api403, 'the page opened with no refusal (security finding)').toBe(true);
  });
}

// TC12: the API itself checks the permission (the page hiding is only for people)
for (const [perm, path] of Object.entries(PERM_API)) {
  test(`TC12 API ${path} answers by permission (${perm})`, async ({ request }) => {
    const me = await getMe(request);
    const res = await request.get(path);
    const has = me.permissions.includes(perm);
    if (res.status() === 404) {
      const body = await res.json().catch(() => ({}));
      test.skip(body?.code === 'module_off', 'area switched off for this account');
    }
    expect(res.status(), has ? `has ${perm}: expected 200` : `lacks ${perm}: expected 403`).toBe(has ? 200 : 403);
  });
}
