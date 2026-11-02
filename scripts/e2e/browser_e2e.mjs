// Real-browser check: headless Chrome via the DevTools protocol (no extra packages).
// Opens every page, records JS errors / failed requests, checks the page heading, clicks a few buttons.
import { spawn } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const WEB = 'http://127.0.0.1:3002';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9333;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const check = (name, ok, info = '') => { results.push({ name, ok, info }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok || !info ? '' : `  -> ${info}`}`); };

const profile = mkdtempSync(join(tmpdir(), 'kjs-e2e-chrome-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, '--no-first-run', '--window-size=1280,900', 'about:blank'], { stdio: 'ignore' });

let targets;
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (targets.length) break; } catch { /* starting */ }
  await sleep(250);
}
const page = targets.find((t) => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));

let id = 0;
const pending = new Map();
let errors = [];
const loaded = [];
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') errors.push(`JS exception: ${m.params.exceptionDetails.exception?.description?.split('\n')[0] ?? m.params.exceptionDetails.text}`);
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push(`console.error: ${m.params.args.map((a) => a.value ?? a.description).join(' ').slice(0, 200)}`);
  if (m.method === 'Network.responseReceived' && m.params.response.status >= 500) errors.push(`HTTP ${m.params.response.status} ${m.params.response.url}`);
  if (m.method === 'Page.loadEventFired') loaded.push(Date.now());
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
const text = () => evaluate('document.body ? document.body.innerText : ""');
async function open(path, waitMs = 2500) {
  errors = [];
  const n = loaded.length;
  await send('Page.navigate', { url: WEB + path });
  for (let i = 0; i < 60 && loaded.length === n; i++) await sleep(250);
  await sleep(waitMs); // let client components fetch their data
  return text();
}
async function waitFor(needle, ms = 6000) {
  for (let t = 0; t < ms; t += 250) { if ((await text()).includes(needle)) return true; await sleep(250); }
  return false;
}
const click = (label) => evaluate(`(() => { const b = [...document.querySelectorAll('button, a')].find(e => e.innerText.trim() === ${JSON.stringify(label)}); if (!b) return false; b.click(); return true; })()`);

await send('Runtime.enable');
await send('Page.enable');
await send('Network.enable');

// ---- Public pages ----
const PUBLIC = { '/': 'Explore the range', '/products': 'Masala Tea Premix', '/private-label': 'Build your product', '/partners': 'Apply to become a partner', '/contact': 'Send an enquiry', '/categories/coffee': 'Instant Coffee', '/employee/login': 'Log in' };
// Everything the page shows, also parts hidden at this width (innerText skips those); scripts left out, as
// they hold the product data and could contain any text
const allText = () => evaluate('(() => { const b = document.body.cloneNode(true); b.querySelectorAll("script, style").forEach((e) => e.remove()); return b.textContent; })()');
let homeAll = '';
let homeCount = null;
let homeGap = null;
let capLinks = [];
for (const [path, needle] of Object.entries(PUBLIC)) {
  const t = await open(path);
  check(`browser ${path}`, t.includes(needle) && errors.length === 0, errors.join(' | ') || `missing "${needle}"`);
  if (path === '/') {
    homeAll = (await allText()) ?? '';
    // Space between the "How it works" section and the green "Launching a product" card below it
    homeGap = await evaluate('(() => { const card = [...document.querySelectorAll("h2")].find((h) => h.textContent.startsWith("Launching a product"))?.closest(".rounded-2xl"); const above = card?.closest("section")?.previousElementSibling; return card && above ? card.getBoundingClientRect().top - above.getBoundingClientRect().bottom : null; })()');
    // The number above "product families in the catalogue" in the dark stats box (null if the line is missing)
    homeCount = await evaluate('[...document.querySelectorAll("p")].find((p) => p.textContent === "product families in the catalogue")?.previousElementSibling?.textContent ?? null');
    capLinks = (await evaluate('[...document.querySelectorAll("footer a[href*=\'/capabilities/\']")].map((a) => [a.getAttribute("href"), a.textContent.trim()])')) ?? [];
  }
}

// Home: no Capabilities section and no "250+" line (UI step 3). Whole sentences only: a bare "250+" could
// be in a product's text
const leftOver = ['One partner from blend to pallet', 'products our two units can make'].filter((s) => homeAll.includes(s));
check('home: Capabilities section and "250+" removed', homeAll !== '' && leftOver.length === 0, homeAll ? `still there: ${leftOver.join(', ')}` : 'could not read the home page');
check('home: space above the green "Launching a product" card', homeGap !== null && homeGap >= 40, `gap: ${homeGap}px`);
// The stats box shows the real product count (the API is up here), never a made-up "50+"
check('home: stats box shows the real product count', /^[1-9]\d*$/.test(homeCount ?? ''), `shows: ${JSON.stringify(homeCount)}`);
// The capability pages themselves stay: every one the footer links to opens with its own heading. The list
// comes from the footer, so a new or renamed page is checked without editing this test
check('footer links to the capability pages', capLinks.length >= 5, `found ${capLinks.length}`);
for (const [href, name] of capLinks) {
  await open(href, 300); // fixed pages, nothing to load after the page itself
  const h1 = (await evaluate('document.querySelector("h1")?.textContent')) ?? '';
  check(`capability page ${href} still opens`, h1.includes(name) && errors.length === 0, errors.join(' | ') || `heading: "${h1}"`);
}

// Partner page (UI step 4): "Broker" is shown as "Referral partner" (saved value still "broker"), no promise of
// a referral link we don't have, and the new sections built from real content
await open('/partners');
// Only the page's own content (not the header, footer, offers ticker or Koko), scripts left out
const partnersAll = (await evaluate('(() => { const m = document.querySelector("main")?.cloneNode(true); if (!m) return ""; m.querySelectorAll("script, style").forEach((e) => e.remove()); return m.textContent; })()')) ?? '';
const brokerOption = await evaluate('document.querySelector("select[name=partner_type] option[value=broker]")?.textContent ?? null');
const partnerProblems = [
  partnersAll === '' && 'could not read the page',
  /broker/i.test(partnersAll) && 'the word "broker" is still shown',
  partnersAll.includes('Your own referral link') && 'the referral-link promise is still there',
  brokerOption !== 'Referral partner' && `the "broker" option says ${JSON.stringify(brokerOption)}`,
].filter(Boolean);
check('partners: "Broker" shown as "Referral partner", no referral-link promise', partnerProblems.length === 0, partnerProblems.join('; '));
const partnerSections = ['Who can apply', 'How it works', 'What your buyers can order'].filter((s) => !partnersAll.includes(s));
check('partners: new sections are there', partnerSections.length === 0, `missing: ${partnerSections.join(', ')}`);
// Links inside the "What your buyers can order" section itself
const buyerLinks = await evaluate('[...document.querySelectorAll("main section")].find((s) => s.querySelector("h2")?.textContent === "What your buyers can order")?.querySelectorAll("a[href*=\'/categories/\']").length ?? 0');
check('partners: buyers section links to real categories', buyerLinks > 0, 'no category links in that section');

// Product page: gated "Get a quote" opens the form (or the one-click view)
await open('/products/instant-coffee-3-in-1-stick');
check('click "Get a quote" opens the form', (await click('Get a quote')) && (await waitFor('Full name')), errors.join(' | '));

// Koko opens and answers
await open('/');
await click('💬 Ask Koko');
const kokoOpen = await waitFor('Koko · KJS assistant');
await evaluate(`(() => { const i = document.querySelector('input[placeholder^="Ask about"]'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(i, 'What certifications do you have?'); i.dispatchEvent(new Event('input', { bubbles: true })); i.form.requestSubmit(); return true; })()`);
const kokoAnswered = await waitFor('ISO', 25000);
check('Koko chat opens and answers in the browser', kokoOpen && kokoAnswered && errors.length === 0, errors.join(' | ') || 'no answer mentioning ISO');

// ---- Log in through the real form ----
await open('/employee/login');
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  const e = document.querySelector('input[type=email]'); const p = document.querySelector('input[type=password]');
  set.call(e, 'admin@e2e.test'); e.dispatchEvent(new Event('input', { bubbles: true }));
  set.call(p, 'e2e-admin-pass-1'); p.dispatchEvent(new Event('input', { bubbles: true }));
  p.form.requestSubmit(); return true; })()`);
check('login form works (admin lands on Admin overview)', await waitFor('Admin overview', 10000), errors.join(' | '));

// ---- Portal pages ----
const PORTAL = {
  '/employee/dashboard': 'My leads', '/employee/attendance': 'Missed a punch?', '/employee/tasks': 'Add task',
  '/employee/batches': 'My batches', '/employee/order-boards': 'My order boards', '/employee/order-boards/E2E117-1': 'Documents',
  '/employee/me': 'Change password', '/admin/dashboard': 'Admin overview', '/admin/leads': 'All leads', '/admin/approvals': 'Approvals',
  '/admin/team-attendance': 'Team attendance', '/admin/order-boards': 'New board', '/admin/order-boards/E2E117-1': 'Packing',
  '/admin/auto-assign': 'Import buyer records', '/admin/products': 'Add a product', '/admin/website': 'Text & SEO', '/admin/koko': 'Recent chats',
  '/admin/holidays': 'Diwali', '/admin/analytics': 'New leads per week', '/admin/alerts': 'Alerts sent', '/admin/audit': 'Audit',
  '/admin/settings': 'respond_minutes',
};
for (const [path, needle] of Object.entries(PORTAL)) {
  await open(path, 500);
  const ok = await waitFor(needle, 8000);
  const t = await text();
  check(`browser ${path}`, ok && errors.length === 0 && !t.includes('Something went wrong'), errors.join(' | ') || `missing "${needle}"`);
}

// Click: check in from My day, and the bell opens
await open('/employee/dashboard', 500);
await waitFor('Check in');
await click('Check in');
check('click "Check in" updates the card', await waitFor('Check out'), errors.join(' | '));
await evaluate(`document.querySelector('button[aria-label^="Notifications"]').click()`);
check('bell opens the notifications list', await waitFor('Mark all read') || await waitFor('Nothing yet'), errors.join(' | '));

// New board form: live plan preview
await open('/admin/order-boards', 500);
await waitFor('New board');
await click('New board');
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  const d = document.querySelectorAll('input[type=date]')[1]; set.call(d, '2026-11-20'); d.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
check('board form shows planned step dates', await waitFor('Planned ', 6000), errors.join(' | '));

// Phone width: menu button exists and opens the sidebar
await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 800, deviceScaleFactor: 2, mobile: true });
await open('/employee/tasks', 500);
await waitFor('Add task');
await evaluate(`document.querySelector('button[aria-label="Open menu"]').click()`);
check('phone: menu opens the sidebar', await waitFor('Attendance'), errors.join(' | '));
const overflow = await evaluate('document.documentElement.scrollWidth > window.innerWidth + 1');
check('phone: no sideways scrolling on tasks page', !overflow);
await open('/', 1500);
check('phone: home has no sideways scrolling', !(await evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')));

ws.close();
chrome.kill();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length} passed, ${failed.length} failed`);
for (const f of failed) console.log(' FAIL:', f.name, '->', f.info);
process.exit(failed.length ? 1 : 0);
