// Staff sidebar, in a real (headless) Chrome: hidden by default, the ☰ button slides it in and out, on a
// computer the page moves aside (and this tab remembers it open), on a phone it slides over the page like a
// dialog. Needs the e2e servers from README.md (frontend on 3002, admin@e2e.test). Read-only: it only logs
// in and opens pages.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const WEB = process.argv[2] || 'http://localhost:3002';
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9393;
const ADMIN = { email: 'admin@e2e.test', password: 'e2e-admin-pass-1' }; // reset_e2e_db.sh
const SLIDE_DONE_MS = 600; // the slide takes 300 ms
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;
const check = (name, ok, info = '') => { if (!ok) failed++; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok || !info ? '' : `  -> ${info}`}`); };

const profile = mkdtempSync(join(tmpdir(), 'kjs-sidebar-e2e-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, '--no-first-run', '--window-size=1280,900', 'about:blank'], { stdio: 'ignore' });
process.on('exit', () => {
  chrome.kill();
  try { rmSync(profile, { recursive: true, force: true, maxRetries: 3 }); } catch { /* Chrome may still hold a file */ }
});
for (let i = 0; i < 40; i++) { try { await fetch(`http://127.0.0.1:${PORT}/json/version`); break; } catch { await sleep(250); } }

/** A browser tab driven over the DevTools protocol. */
async function tab(url = 'about:blank') {
  const t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${url}`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r));
  let id = 0;
  const pending = new Map();
  const tb = { errors: [], loaded: 0, id: t.id };
  tb.send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  ws.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === 'Runtime.exceptionThrown') tb.errors.push(m.params.exceptionDetails.exception?.description?.split('\n')[0] ?? m.params.exceptionDetails.text);
    if (m.method === 'Page.loadEventFired') tb.loaded++;
  });
  await tb.send('Runtime.enable');
  await tb.send('Page.enable');
  tb.evaluate = async (expr) => (await tb.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
  tb.close = async () => { ws.close(); await fetch(`http://127.0.0.1:${PORT}/json/close/${t.id}`); };
  return tb;
}

const A = await tab();
const evaluate = A.evaluate;
const send = A.send;
const open = async (path) => { const n = A.loaded; await send('Page.navigate', { url: WEB + path }); for (let i = 0; i < 120 && A.loaded === n; i++) await sleep(250); await sleep(1500); };
const waitText = async (text, ms, T = A) => { for (let i = 0; i < ms / 250; i++) { if (await T.evaluate(`document.body.innerText.includes(${JSON.stringify(text)})`)) return true; await sleep(250); } return false; };
const waitPath = async (path) => { for (let i = 0; i < 40 && (await evaluate('location.pathname')) !== path; i++) await sleep(250); return (await evaluate('location.pathname')) === path; };
const size = (width, height, mobile) => send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: mobile ? 3 : 1, mobile });
const STATE = `(() => {
  const a = document.getElementById('portal-sidebar'); const b = document.querySelector('button[aria-controls="portal-sidebar"]');
  if (!a || !b) return { missing: 'no hideable sidebar or menu button on this page' }; // every check then fails
  const r = a.getBoundingClientRect();
  const d = document.querySelector('div.fixed.inset-0.z-30');
  return { left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width), inert: a.inert,
    expanded: b.getAttribute('aria-expanded'), label: b.getAttribute('aria-label'),
    headerLeft: Math.round(document.querySelector('header').getBoundingClientRect().left),
    backdrop: !!d && getComputedStyle(d).display !== 'none',
    scrollX: document.documentElement.scrollWidth > innerWidth,
    transition: getComputedStyle(a).transitionProperty,
    // Is a slide running right now? Asked of the browser itself, no timing guess
    sliding: a.getAnimations().some((x) => x.transitionProperty === 'transform' && x.playState === 'running'),
    pageInert: !!document.querySelector('header').closest('[inert]'),
    bodyLocked: getComputedStyle(document.body).overflow === 'hidden',
    focus: document.activeElement?.getAttribute('aria-controls') || document.activeElement?.tagName };
})()`;
const state = () => evaluate(STATE);
const toggle = () => evaluate(`document.querySelector('button[aria-controls="portal-sidebar"]').click()`);
// The sidebar's groups can be closed (they start closed): open them first if the link isn't shown
const clickLink = async (text) => {
  const find = `[...document.querySelectorAll('#portal-sidebar a')].find((a) => a.textContent.trim().startsWith(${JSON.stringify(text)}))`;
  if (!(await evaluate(`!!${find}`))) {
    await evaluate(`document.querySelectorAll('#portal-sidebar button[aria-expanded="false"][aria-controls]').forEach((b) => b.click())`);
    await sleep(300);
  }
  return evaluate(`${find}.click()`);
};
const key = async (k) => { await send('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code: k }); await send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code: k }); };

// ---------- log in (through the API, from our own page) ----------
await open('/employee/login');
const login = await evaluate(`fetch('/api/v1/auth/login', { method: 'POST', headers: { 'content-type': 'application/json', 'x-requested-with': 'kjs' },
  body: JSON.stringify(${JSON.stringify(ADMIN)}) }).then((r) => r.status)`);
check('setup: logged in as the e2e admin', login === 200, `status ${login} (429 = too many wrong passwords from login_e2e: restart the backend)`);

// ---------- computer (1280 px) ----------
await open('/admin/dashboard');
check('setup: the admin page is open', await waitText('Live numbers', 15000));
let s = await state();
check('computer: hidden by default (off screen, not reachable with Tab)', s.right <= 0 && s.inert === true && s.expanded === 'false' && s.label === 'Open menu', JSON.stringify(s));
check('computer: the page uses the full width while it is hidden', s.headerLeft === 0, JSON.stringify(s));
await toggle();
s = await state();
check('computer: a click starts a slide-in', s.sliding, JSON.stringify(s));
await sleep(SLIDE_DONE_MS);
s = await state();
check('computer: then open: in view, reachable, the button says "Close menu"', s.left === 0 && s.inert === false && s.expanded === 'true' && s.label === 'Close menu', JSON.stringify(s));
check('computer: the page moved aside (not covered, not locked), no sideways scrolling', s.headerLeft >= s.width - 1 && !s.backdrop && !s.pageInert && !s.bodyLocked && !s.scrollX, JSON.stringify(s));
await clickLink('All leads');
await waitPath('/admin/leads');
await sleep(SLIDE_DONE_MS);
s = await state();
check('computer: opening a page from it keeps it open', s.left === 0, JSON.stringify(s));
// Admin -> employee pages have another frame: the choice is remembered, and it is simply there (no slide)
await clickLink('My day');
await waitPath('/employee/dashboard');
await waitText('My leads', 15000);
s = await state();
check('computer: still open on an employee page (another frame), without sliding in again', s.left === 0 && !s.sliding, JSON.stringify(s));
await open('/admin/dashboard');
await waitText('Live numbers', 15000);
s = await state();
check('computer: still open after a reload (this tab remembers)', s.left === 0 && !s.sliding, JSON.stringify(s));
// An Escape meant for something else (focus outside the sidebar) leaves it alone
await evaluate(`[...document.querySelectorAll('header button')].find((b) => b.textContent.trim() === 'Log out').focus()`);
await key('Escape');
await sleep(SLIDE_DONE_MS);
s = await state();
check('computer: Escape pressed elsewhere leaves it open', s.left === 0, JSON.stringify(s));
await evaluate(`document.querySelector('#portal-sidebar a').focus()`);
await key('Escape');
await sleep(SLIDE_DONE_MS);
s = await state();
check('computer: Escape in the sidebar closes it, focus on the menu button', s.right <= 0 && s.focus === 'portal-sidebar', JSON.stringify(s));
await toggle();
await sleep(SLIDE_DONE_MS);
await toggle();
s = await state();
check('computer: the next click starts a slide-out', s.sliding, JSON.stringify(s));
await sleep(SLIDE_DONE_MS);
s = await state();
check('computer: hidden again, the page takes the full width', s.right <= 0 && s.inert === true && s.headerLeft === 0, JSON.stringify(s));
// A new tab starts hidden (only this tab remembers), even with this one open
await toggle();
await sleep(SLIDE_DONE_MS);
const B = await tab(encodeURIComponent(WEB + '/admin/dashboard'));
await waitText('Live numbers', 15000, B);
const other = await B.evaluate(STATE);
await B.close();
check('computer: a new tab starts with it hidden', other.right <= 0, JSON.stringify(other));

// ---------- phone (390 px): it is open in this tab's memory now, but must not reopen on a phone ----------
await size(390, 844, true);
await open('/admin/dashboard');
await waitText('Live numbers', 15000);
s = await state();
check('phone: hidden by default (never reopened from memory), no sideways scrolling', s.right <= 0 && s.inert === true && !s.scrollX, JSON.stringify(s));
await toggle();
await sleep(SLIDE_DONE_MS);
s = await state();
check('phone: it slides OVER the page (not pushed), with a backdrop', s.left === 0 && s.headerLeft === 0 && s.backdrop && !s.scrollX, JSON.stringify(s));
check('phone: the page behind is locked (no scrolling, not reachable with Tab)', s.pageInert && s.bodyLocked, JSON.stringify(s));
const ownClose = await evaluate(`(() => { const b = document.querySelector('#portal-sidebar button[aria-label="Close menu"]'); if (!b) return null; const r = b.getBoundingClientRect(); return getComputedStyle(b).display !== 'none' && r.width > 0 && r.right <= innerWidth; })()`);
check('phone: the sidebar has its own ✕ (the top bar one is covered)', ownClose === true, String(ownClose));
await evaluate(`document.querySelector('#portal-sidebar button[aria-label="Close menu"]').click()`);
await sleep(SLIDE_DONE_MS);
s = await state();
check('phone: its ✕ closes it, unlocks the page, focus back on the menu button', s.right <= 0 && !s.pageInert && !s.bodyLocked && s.focus === 'portal-sidebar', JSON.stringify(s));
await toggle();
await sleep(SLIDE_DONE_MS);
await evaluate(`document.querySelector('div.fixed.inset-0.z-30').click()`);
await sleep(SLIDE_DONE_MS);
s = await state();
check('phone: tapping the backdrop closes it', s.right <= 0 && !s.backdrop, JSON.stringify(s));
await toggle();
await sleep(SLIDE_DONE_MS);
await clickLink('All leads');
await waitPath('/admin/leads');
await sleep(SLIDE_DONE_MS);
s = await state();
check('phone: choosing a page closes it (and opens the page)', s.right <= 0 && !s.bodyLocked, JSON.stringify(s));

// ---------- reduced motion ----------
await size(1280, 900, false);
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
await evaluate(`sessionStorage.removeItem('kjs_menu_open')`);
await open('/admin/dashboard');
await waitText('Live numbers', 15000);
s = await state();
check('reduced motion: no slide animation', s.transition === 'none', s.transition);
await toggle();
await sleep(50);
s = await state();
check('reduced motion: it still opens (at once)', s.left === 0 && !s.sliding, JSON.stringify(s));

check('no browser errors', A.errors.length === 0, A.errors.join(' | '));
console.log(`\n${failed ? `${failed} FAILED` : 'all passed'}`);
process.exit(failed ? 1 : 0);
