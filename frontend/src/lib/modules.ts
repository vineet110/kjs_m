// Portal areas switched on and off for phased releases (config/modules.ini; backend app/core/modules.py).
// The server works out what each person may see and sends it in "who am I" (`me.modules`); this file only
// reads that answer. The API refuses a hidden area anyway (404 `module_off`): hiding it here is for people,
// not for safety.
import type { Me } from './api';

export type Area = 'batches' | 'order_boards' | 'attendance' | 'website_admin' | 'analytics' | 'alerts' | 'audit';

// Portal pages of each area (the start of the path). Keep in step with AREA_PAGES in app/core/modules.py.
const AREA_PAGES: Record<Area, string[]> = {
  batches: ['/employee/batches', '/admin/auto-assign'],
  order_boards: ['/employee/order-boards', '/admin/order-boards'],
  attendance: ['/employee/attendance', '/admin/team-attendance', '/admin/holidays'],
  website_admin: ['/admin/products', '/admin/website', '/admin/koko'],
  analytics: ['/admin/analytics'],
  alerts: ['/admin/alerts'],
  audit: ['/admin/audit'],
};

/** Can this person use the area? Not in the answer (an older server) = yes. */
export function canSee(me: Pick<Me, 'modules'>, area: Area | null | undefined): boolean {
  return !area || me.modules?.[area] !== false;
}

/** The area a portal path belongs to ("/en/employee/order-boards/X" -> "order_boards"), or null. */
export function areaOfPath(path: string): Area | null {
  const p = path.replace(/^\/[a-z]{2}(?=\/)/, '').split(/[?#]/)[0]; // without "/en" and "?..."
  for (const [area, pages] of Object.entries(AREA_PAGES) as [Area, string[]][]) {
    if (pages.some((start) => p === start || p.startsWith(`${start}/`))) return area;
  }
  return null;
}

// ----- "The server says this area is hidden" -----
// api() sends this when an answer is 404 `module_off` (an area switched off while the page was open). The
// portal frame listens: it asks "who am I" again (new sidebar) and shows "Not available yet".
const MODULE_OFF = 'kjs:module-off';

export function moduleOff() {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(MODULE_OFF));
}

/** Calls `fn` on every moduleOff(); returns the function that stops listening. */
export function onModuleOff(fn: () => void) {
  window.addEventListener(MODULE_OFF, fn);
  return () => window.removeEventListener(MODULE_OFF, fn);
}
