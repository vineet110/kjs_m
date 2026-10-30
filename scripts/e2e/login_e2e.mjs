// Login loading states, in a real (headless) Chrome: the spinner, the time limits and the error screen.
// Needs the e2e servers from README.md (frontend on 3002, admin@e2e.test). Some requests are held back on
// purpose (DevTools "Fetch"), so slow or silent servers can be tested; nothing is changed on the server.
// To see it catch a bug: run it on code without the spinner (git stash, rebuild): checks fail.
import { spawn } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const WEB = process.argv[2] || 'http://localhost:3002';
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9391;
const ADMIN = { email: 'admin@e2e.test', password: 'e2e-admin-pass-1' }; // reset_e2e_db.sh
const SLOW_MS = 1500; // login and "who am I" are slowed by this much, so the loading states can be seen
const PAST_LIMIT_MS = 17_000; // longer than the app's 15 s limits (PortalShell ME_TIMEOUT_MS, login PAGE_OPEN_LIMIT_MS)
const SLOW_PAGE_MS = 26_000; // the "slow" next page: long enough to try again while it is still opening
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;
const check = (name, ok, info = '') => { if (!ok) failed++; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok || !info ? '' : `  -> ${info}`}`); };

const profile = mkdtempSync(join(tmpdir(), 'kjs-login-e2e-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, '--no-first-run', '--window-size=1280,900', 'about:blank'], { stdio: 'ignore' });
process.on('exit', () => chrome.kill()); // also when a step crashes: no Chrome left running on the port
for (let i = 0; i < 40; i++) { try { await fetch(`http://127.0.0.1:${PORT}/json/version`); break; } catch { await sleep(250); } }

const t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' })).json();
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0;
const pending = new Map();
const errors = [];
let loaded = 0;
// What to do with held requests: "who am I" can fail (502) or never answer; the next page can be slow
const mode = { meFail: 0, meSilent: false, pageSlow: false, logoutSilent: false };
const held = [];
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.exception?.description?.split('\n')[0] ?? m.params.exceptionDetails.text);
  if (m.method === 'Page.loadEventFired') loaded++;
  if (m.method !== 'Fetch.requestPaused') return;
  const { requestId, request } = m.params;
  const go = (ms) => setTimeout(() => send('Fetch.continueRequest', { requestId }), ms);
  held.push(request.url);
  if (request.url.includes('_rsc=')) return go(mode.pageSlow && request.url.includes('/dashboard') ? SLOW_PAGE_MS : 0);
  if (request.url.includes('/auth/logout')) return go(mode.logoutSilent ? PAST_LIMIT_MS : 0);
  if (request.url.includes('/auth/me')) {
    if (mode.meFail > 0) {
      mode.meFail--;
      return send('Fetch.fulfillRequest', { requestId, responseCode: 502, responseHeaders: [{ name: 'Content-Type', value: 'text/html' }], body: Buffer.from('Bad gateway').toString('base64') });
    }
    return go(mode.meSilent ? PAST_LIMIT_MS : SLOW_MS);
  }
  go(SLOW_MS); // /auth/login
});
await send('Runtime.enable');
await send('Page.enable');
await send('Fetch.enable', { patterns: [{ urlPattern: '*/api/v1/auth/login*' }, { urlPattern: '*/api/v1/auth/me*' }, { urlPattern: '*/api/v1/auth/logout*' }, { urlPattern: '*_rsc=*' }] });
const evaluate = async (expr) => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
const open = async (path) => { const n = loaded; await send('Page.navigate', { url: WEB + path }); for (let i = 0; i < 120 && loaded === n; i++) await sleep(250); await sleep(1500); };
const logout = () => evaluate(`fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'x-requested-with': 'kjs' } }).then(() => 1)`);
const fill = (password) => evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  const e = document.querySelector('input[type=email]'); const p = document.querySelector('input[type=password]');
  set.call(e, ${JSON.stringify(ADMIN.email)}); e.dispatchEvent(new Event('input', { bubbles: true }));
  set.call(p, ${JSON.stringify(password)}); p.dispatchEvent(new Event('input', { bubbles: true }));
  p.form.requestSubmit(); return true; })()`);
const button = () => evaluate(`(() => { const b = document.querySelector('form button:not([type=button])'); return b ? { text: b.textContent.trim(), disabled: b.disabled, spinner: !!b.querySelector('.animate-spin') } : null; })()`);
const waitText = async (text, ms) => { for (let i = 0; i < ms / 250; i++) { if (await evaluate(`document.body.innerText.includes(${JSON.stringify(text)})`)) return true; await sleep(250); } return false; };

// ---------- 1. wrong password: spinner while waiting, then the error and the form back ----------
await open('/employee/login');
let b = await button();
check('1 setup: the login form is there, no spinner', b && b.text === 'Log in' && !b.spinner && !b.disabled, JSON.stringify(b));
await fill('wrong-password-123');
await sleep(400);
b = await button();
check('1 while logging in: spinner, button locked, "Logging in…"', b.spinner && b.disabled && b.text === 'Logging in…', JSON.stringify(b));
const tabs = await evaluate(`[...document.querySelectorAll('button')].filter(x => !x.closest('form') && ['Log in', 'Sign up'].includes(x.textContent.trim())).map(x => ({ disabled: x.disabled, opacity: getComputedStyle(x).opacity }))`);
check('1 while logging in: the Log in / Sign up tabs are locked and look it (faded)', tabs.length === 2 && tabs.every((x) => x.disabled && Number(x.opacity) < 1), JSON.stringify(tabs));
await sleep(SLOW_MS + 1000);
b = await button();
check('1 after a failed login: spinner gone, button ready, "Log in"', !b.spinner && !b.disabled && b.text === 'Log in', JSON.stringify(b));
check('1 the error message is shown', ((await evaluate(`document.querySelector('form .bg-red-50')?.textContent`)) ?? '').length > 0);

// ---------- 2. right password: the spinner stays until the dashboard opens (no flash back) ----------
await evaluate(`(() => { window.__btn = []; const tick = () => { const x = document.querySelector('form button:not([type=button])');
  if (x) window.__btn.push(x.textContent.trim() + (x.querySelector('.animate-spin') ? '+spin' : '')); if (document.querySelector('form')) requestAnimationFrame(tick); }; tick(); return 1; })()`);
await fill(ADMIN.password);
let samples = [];
for (let i = 0; i < 120; i++) {
  const s = await evaluate(`({ gone: !document.querySelector('form'), samples: window.__btn.slice() })`);
  samples = s.samples;
  if (s.gone) break;
  await sleep(30);
}
const firstBusy = samples.indexOf('Logging in…+spin');
check('2 the button never flashes back to "Log in" before the page changes', firstBusy >= 0 && samples.slice(firstBusy).every((x) => x === 'Logging in…+spin'), JSON.stringify([...new Set(samples)]));
let spinning = false;
for (let i = 0; i < 60 && !spinning; i++) { spinning = await evaluate(`!!document.querySelector('[role=status] .animate-spin')`); await sleep(50); }
check('2 the account loading screen shows the spinner', spinning);
check('2 the admin lands on Admin overview', await waitText('Admin overview', 15000));

// ---------- 3. "who am I" fails (502): error screen with Try again, Log out and an error code ----------
mode.meFail = 1;
await open('/admin/dashboard');
await sleep(500);
const alert = await evaluate(`(() => { const a = document.querySelector('[role=alert]'); return a ? { text: a.innerText, buttons: [...a.querySelectorAll('button')].map(x => x.textContent.trim()), code: a.querySelector('.font-mono')?.textContent ?? '' } : null; })()`);
check('3 a server error shows a message, not an endless spinner', alert?.text.includes('Could not load your account'), JSON.stringify(alert));
check('3 the error screen offers Try again AND Log out', alert && alert.buttons.includes('Try again') && alert.buttons.includes('Log out'), JSON.stringify(alert?.buttons));
check('3 the error screen shows a code for support', alert && alert.code.length >= 8, alert?.code);
await evaluate(`[...document.querySelectorAll('[role=alert] button')].find(x => x.textContent.includes('Try again')).click()`);
await sleep(300);
check('3 "Try again" shows the spinner while it asks again (the error is gone)', await evaluate(`!!document.querySelector('[role=status] .animate-spin') && !document.querySelector('[role=alert]')`));
check('3 "Try again" then loads the page', await waitText('Admin overview', 10000));

// ---------- 4. "who am I" never answers: after the time limit, the error screen (not loading forever) ----------
mode.meSilent = true;
await open('/admin/dashboard');
check('4 setup: still loading while the server is silent', await evaluate(`!!document.querySelector('[role=status] .animate-spin')`));
check('4 after the time limit: the error screen, with Try again and Log out', await waitText('Could not load your account', PAST_LIMIT_MS));
mode.meSilent = false;
mode.logoutSilent = true; // the server is still silent: Log out must not hang
await evaluate(`[...document.querySelectorAll('[role=alert] button')].find(x => x.textContent.includes('Log out')).click()`);
for (let i = 0; i < 48 && (await evaluate('location.pathname')) !== '/employee/login'; i++) await sleep(250);
check('4 "Log out" from the error screen goes to the login page, even with a silent server', (await evaluate('location.pathname')) === '/employee/login');
mode.logoutSilent = false;
await sleep(PAST_LIMIT_MS - 12_000); // let the held log-out reach the server (so the next steps start logged out)
await logout();

// ---------- 5. the next page is slow to open: the form is given back with a link ----------
mode.pageSlow = true;
await open('/employee/login');
await fill(ADMIN.password);
check('5 after the time limit: "the page is slow to open" with a link', await waitText('slow to open', PAST_LIMIT_MS));
b = await button();
const link = await evaluate(`document.querySelector('a[href="/admin/dashboard"]')?.textContent ?? ''`);
check('5 the button is ready again (not locked until a reload), and the link opens the dashboard', b && !b.disabled && !b.spinner && link === 'Open it', `${JSON.stringify(b)} link=${link}`);
// While that page is still opening: the Sign up tab hides the notice; a failed new attempt doesn't lock the form
await evaluate(`[...document.querySelectorAll('button')].find(x => !x.closest('form') && x.textContent.trim() === 'Sign up').click()`);
await sleep(200);
check('5 switching to Sign up hides the "logged in, slow to open" notice', !(await evaluate(`document.body.innerText.includes('slow to open')`)));
await evaluate(`[...document.querySelectorAll('button')].find(x => !x.closest('form') && x.textContent.trim() === 'Log in').click()`);
await sleep(200);
await fill('wrong-password-123');
await sleep(SLOW_MS + 1200);
b = await button();
check('5 a failed new attempt while the old page is still opening: the form is ready (not locked)', b && !b.disabled && !b.spinner && b.text === 'Log in', JSON.stringify(b));
mode.pageSlow = false;
await sleep(SLOW_PAGE_MS - 18_000);
await logout();

// ---------- 6. a login link that points back to the login page: go to the dashboard instead ----------
await open('/employee/login?next=%2Femployee%2Flogin');
await fill(ADMIN.password);
check('6 next=/employee/login: logging in opens the dashboard (not the form again)', await waitText('Admin overview', 15000));
await logout();

// ---------- 7. reduced motion: the ring is shown but doesn't spin ----------
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
await open('/employee/login');
await fill('wrong-password-123');
await sleep(400);
const anim = await evaluate(`(() => { const s = document.querySelector('form button .animate-spin'); return s ? getComputedStyle(s).animationName : 'no spinner'; })()`);
check('7 with "reduce motion", the spinner is shown but does not spin', anim === 'none', anim);
await sleep(SLOW_MS + 800);

check('setup: the requests were really held back', held.some((u) => u.includes('/auth/login')) && held.some((u) => u.includes('/auth/me')));
check('no browser errors', errors.length === 0, errors.join(' | '));
console.log(`\n${failed ? `${failed} FAILED` : 'all passed'}`);
chrome.kill();
process.exit(failed ? 1 : 0);
