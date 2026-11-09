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
let homeBest = null;
let homeRecommended = null;
for (const [path, needle] of Object.entries(PUBLIC)) {
  const t = await open(path);
  check(`browser ${path}`, t.includes(needle) && errors.length === 0, errors.join(' | ') || `missing "${needle}"`);
  if (path === '/') {
    homeAll = (await allText()) ?? '';
    // Space between the "How it works" section and the green "Launching a product" card below it
    homeGap = await evaluate('(() => { const card = [...document.querySelectorAll("h2")].find((h) => h.textContent.startsWith("Launching a product"))?.closest(".rounded-2xl"); const above = card?.closest("section")?.previousElementSibling; return card && above ? card.getBoundingClientRect().top - above.getBoundingClientRect().bottom : null; })()');
    // The text of the "Best sellers" section (null if there is none)
    homeBest = await evaluate('document.getElementById("best-sellers-title")?.closest("section")?.textContent ?? null');
    homeRecommended = await evaluate('document.getElementById("recommended-title")?.closest("section")?.textContent ?? null');
    // The number above "product families in the catalogue" in the dark stats box (null if the line is missing)
    homeCount = await evaluate('[...document.querySelectorAll("p")].find((p) => p.textContent === "product families in the catalogue")?.previousElementSibling?.textContent ?? null');
    capLinks = (await evaluate('[...document.querySelectorAll("a[href*=\'/capabilities/\']")].map((a) => [a.getAttribute("href"), a.textContent.trim()])')) ?? [];
  }
}

// Home: no Capabilities section and no "250+" line (UI step 3). Whole sentences only: a bare "250+" could
// be in a product's text
const leftOver = ['One partner from blend to pallet', 'products our two units can make'].filter((s) => homeAll.includes(s));
check('home: Capabilities section and "250+" removed', homeAll !== '' && leftOver.length === 0, homeAll ? `still there: ${leftOver.join(', ')}` : 'could not read the home page');
check('home: space above the green "Launching a product" card', homeGap !== null && homeGap >= 40, `gap: ${homeGap}px`);
// Best sellers (UI step 5): only the products ticked "Best seller" in Admin > Products. The API suite ticks
// "Instant Coffee 3-in-1 Stick" and not "Masala Tea Premix"
check('home: best sellers section shows only ticked products', homeBest !== null && homeBest.includes('Instant Coffee 3-in-1 Stick') && !homeBest.includes('Masala Tea Premix'), `section: ${JSON.stringify(homeBest?.slice(0, 120) ?? null)}`);
// ...and Recommended, right below, doesn't show them again
check('home: Recommended does not repeat the best sellers', homeRecommended !== null && !homeRecommended.includes('Instant Coffee 3-in-1 Stick'), `recommended: ${JSON.stringify(homeRecommended?.slice(0, 120) ?? null)}`);
// The stats box shows the real product count (the API is up here), never a made-up "50+"
check('home: stats box shows the real product count', /^[1-9]\d*$/.test(homeCount ?? ''), `shows: ${JSON.stringify(homeCount)}`);
// The capability pages are removed for now: no link to them is left in the header or footer
check('no links to the removed capability pages', capLinks.length === 0, `still linked: ${capLinks.map(([h]) => h).join(', ')}`);

// Offer badge (UI step 6): "Up to 15% OFF" on the coffee product (the API suite sets 15 %), on no other card,
// on the home page, the products page and the product page
const badgesOn = (name) => evaluate(`[...document.querySelectorAll("article, a.card")].filter((c) => c.textContent.includes(${JSON.stringify(name)})).map((c) => c.textContent.includes("Up to 15% OFF"))`);
const offerProblems = [];
for (const path of ['/', '/products']) {
  await open(path, path === '/' ? 2500 : 1000);
  const coffee = (await badgesOn('Instant Coffee 3-in-1 Stick')) ?? [];
  const tea = (await badgesOn('Masala Tea Premix')) ?? [];
  if (!coffee.length || !coffee.every(Boolean)) offerProblems.push(`${path}: coffee card badges ${JSON.stringify(coffee)}`);
  if (tea.some(Boolean)) offerProblems.push(`${path}: tea card has a badge`);
}
// The home range card's quick-view button tells screen readers about the offer, and the quick view shows it
await open('/', 2500);
const quickLabel = await evaluate('document.querySelector("button[aria-label^=\'Quick view: Instant Coffee 3-in-1 Stick\']")?.getAttribute("aria-label") ?? null');
if (quickLabel !== 'Quick view: Instant Coffee 3-in-1 Stick, Up to 15% OFF') offerProblems.push(`quick-view label: ${JSON.stringify(quickLabel)}`);
await evaluate('document.querySelector("button[aria-label^=\'Quick view: Instant Coffee 3-in-1 Stick\']")?.click()');
if (!(await waitFor('Up to 15% OFF', 3000)) || !(await evaluate('document.querySelector("[role=dialog]")?.textContent.includes("Up to 15% OFF") ?? false'))) offerProblems.push('quick view: no badge');
const productPage = await open('/products/instant-coffee-3-in-1-stick', 1000);
if (!productPage.includes('Up to 15% OFF')) offerProblems.push('product page: no badge');
if ((await open('/products/masala-tea-premix', 1000)).includes('% OFF')) offerProblems.push('tea product page has a badge');
check('offer badge shows only on the product with an offer', offerProblems.length === 0, offerProblems.join('; '));

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

// Phone code and country pickers (UI step 7), on the contact page's enquiry form and the partner form
const typeInto = (selector, text) => evaluate(`(() => { const i = document.querySelector(${JSON.stringify(selector)}); if (!i) return false; i.focus(); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(i, ${JSON.stringify(text)}); i.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const options = () => evaluate('[...document.querySelectorAll("[role=listbox] [role=option]")].map((o) => o.textContent)');
const hiddenValue = (name, form = 'form') => evaluate(`document.querySelector(${JSON.stringify(`${form} input[name=${name}]`)})?.value ?? null`);
const pressEnter = () => evaluate('(() => { const i = document.activeElement; i.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); return true; })()');
const pickerProblems = [];
await open('/contact', 1500);
const codeButton = 'button[aria-label^="Country code"]';
const startLabel = await evaluate(`document.querySelector('${codeButton}')?.getAttribute("aria-label") ?? null`);
if (!startLabel?.endsWith('India +91')) pickerProblems.push(`starts on ${JSON.stringify(startLabel)}, not India`);
await evaluate(`document.querySelector('${codeButton}')?.click()`);
await sleep(300);
// A flag picture really loaded (a missing file has no width)
const flagOk = await evaluate('new Promise((r) => { let n = 0; const t = setInterval(() => { const img = document.querySelector("[role=listbox] img"); if ((img && img.complete && img.naturalWidth > 0) || ++n > 20) { clearInterval(t); r(!!img && img.naturalWidth > 0); } }, 150); })');
if (!flagOk) pickerProblems.push('no flag pictures in the list');
await typeInto('[role=combobox]', 'a');
await sleep(200);
const aList = (await options()) ?? [];
if (aList.length < 5 || !aList.every((t) => t.normalize('NFD').toLowerCase().startsWith('a'))) pickerProblems.push(`"a" shows: ${aList.slice(0, 5).join(', ')}`);
await typeInto('[role=combobox]', '9');
await sleep(200);
const nineList = (await options()) ?? [];
if (nineList.length < 5 || !nineList.every((t) => /\+9\d*$/.test(t))) pickerProblems.push(`"9" shows: ${nineList.slice(0, 5).join(', ')}`);
await typeInto('[role=combobox]', 'united arab');
await sleep(200);
await pressEnter();
await sleep(200);
await typeInto('#phone', '50 123 4567');
await sleep(200);
const phoneSent = await hiddenValue('phone');
if (phoneSent !== '+971 50 123 4567') pickerProblems.push(`phone sent as ${JSON.stringify(phoneSent)}`);
await typeInto('#phone', 'call me');
if (await evaluate('document.querySelector("#phone").checkValidity()')) pickerProblems.push('"call me" accepted as a phone');
// The phone is required: an empty one stops the form
await typeInto('#phone', '');
if (await evaluate('document.querySelector("#phone").checkValidity()')) pickerProblems.push('empty phone accepted');
// Partner form: picking the country also sets the phone code (until the visitor picks a code)
await open('/partners', 1500);
await evaluate('document.querySelector("#p-country")?.click()');
await sleep(300);
await typeInto('[role=combobox]', 'germ');
await sleep(200);
await pressEnter();
await sleep(300);
const countrySent = await hiddenValue('country');
const codeNow = await evaluate(`document.querySelector('${codeButton}')?.getAttribute("aria-label") ?? null`);
if (countrySent !== 'Germany') pickerProblems.push(`country sent as ${JSON.stringify(countrySent)}`);
if (!codeNow?.endsWith('Germany +49')) pickerProblems.push(`phone code didn't follow the country: ${JSON.stringify(codeNow)}`);
// Sending the partner form without a country says so next to the picker
await open('/partners', 1500);
await evaluate('document.querySelector("form button.btn-gold")?.click()');
await sleep(300);
if (!(await evaluate('[...document.querySelectorAll("[role=alert]")].some((a) => a.textContent.includes("Please choose a country"))'))) pickerProblems.push('no "Please choose a country" message');
// Staff sign-up has the phone picker too
await open('/employee/login', 1000);
await click('Sign up');
await sleep(300);
if (!(await evaluate(`!!document.querySelector('${codeButton}')`))) pickerProblems.push('sign-up has no phone code picker');
check('phone code and country pickers work (search, codes, flags, linked code, light check)', pickerProblems.length === 0 && errors.length === 0, [...pickerProblems, ...errors].join('; '));

// Product page: gated "Get a quote" opens the form (or the one-click view)
await open('/products/instant-coffee-3-in-1-stick');
check('click "Get a quote" opens the form', (await click('Get a quote')) && (await waitFor('Full name')), errors.join(' | '));

// A returning visitor whose remembered phone is free text from before the phone check (PR #16 review):
// no one-click send (the server would refuse it), the form asks for the number again; closing it and
// coming back asks again (never a one-click send with no way to reach them)
await evaluate(`localStorage.setItem('kjs_visitor', JSON.stringify({ name: 'Old Visitor', company: '', email: '', phone: 'call me after 6', country: '' }))`);
const badPhoneTries = [];
for (let visit = 1; visit <= 2; visit++) {
  await open('/products/instant-coffee-3-in-1-stick');
  const clicked = await click('Get a quote');
  const askedAgain = clicked && (await waitFor('Please re-enter your phone number', 4000));
  const oneClick = await evaluate('document.body.innerText.includes("We will send this request as")');
  if (!askedAgain || oneClick) badPhoneTries.push(`visit ${visit}: asked again ${askedAgain}, one-click ${oneClick}`);
}
check('old remembered phone: asks again instead of a one-click send that would fail', badPhoneTries.length === 0, badPhoneTries.join('; '));
await evaluate(`localStorage.removeItem('kjs_visitor')`);

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
check('login form works (admin lands on the admin dashboard)', await waitFor('Live numbers', 10000), errors.join(' | '));

// ---- Portal pages ----
const PORTAL = {
  '/employee/dashboard': 'My leads', '/employee/attendance': 'Total Hours', '/employee/tasks': 'Add task',
  '/employee/batches': 'My batches', '/employee/order-boards': 'My order boards', '/employee/order-boards/E2E117-1': 'Files',
  '/employee/contacts': 'Kiran Rao', '/employee/internal-leads': 'Kiran Rao', '/employee/koko-leads': 'Koko',
  '/employee/me': 'Change password', '/admin/dashboard': 'Live numbers', '/admin/users': 'Gita', '/admin/leads': 'All leads', '/admin/approvals': 'Approvals',
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

// ---- Lead management (PR #33): contact page, its notes and tasks (data from api_e2e.py) ----
const clickText = (label) => evaluate(`(() => { const b = [...document.querySelectorAll('button, a, [role=tab]')].find((e) => e.innerText.trim() === ${JSON.stringify(label)}); if (!b) return false; b.click(); return true; })()`);
await open('/employee/contacts', 500);
await waitFor('Kiran Rao');
await clickText('Kiran Rao');
const contactOk = await waitFor('Rao Foods', 8000);
await clickText('Notes');
const noteOk = await waitFor('Prefers WhatsApp', 4000);
await clickText('Task');
const taskOk = await waitFor('Send samples to Kiran', 4000);
check('contact page: details, notes and tasks', contactOk && noteOk && taskOk && errors.length === 0, errors.join(' | ') || `details ${contactOk}, notes ${noteOk}, tasks ${taskOk}`);

// ---- Order boards (PRs #35-#39): file previews, full screen, History, People, plan lock ----
const BOARD = '/admin/order-boards/E2E117-1';
const openTab = async (start) => { await evaluate(`[...document.querySelectorAll('[role=tab]')].find((e) => e.innerText.trim().startsWith(${JSON.stringify(start)}))?.click()`); await sleep(1200); };
const preview = async (name) => { await clickText(name); await sleep(2500); };
await open(BOARD, 2500);
await openTab('Files');
await preview('rates-hindi.csv');
let pt = await text();
check('board preview: CSV shows Hindi and ₹ as written', pt.includes('कॉफ़ी स्टिक') && pt.includes('₹ 2.50') && pt.includes('₹ 1,250'), pt.slice(-200));
await preview('plan.xlsx');
pt = await text();
const sheetOk = pt.includes('Coffee stick') && pt.includes('Rate (₹)');
await clickText('Notes');
await sleep(500);
check('board preview: Excel table and its second sheet', sheetOk && (await text()).includes('दूसरी शीट'), pt.slice(-200));
await preview('po-117.docx');
const doc = (await evaluate(`(() => { const f = document.querySelector('iframe[srcdoc]'); return f ? { html: f.srcdoc, sandbox: f.getAttribute('sandbox') } : null; })()`)) ?? {};
check('board preview: Word in a sandboxed frame (text, Hindi, table)', doc.sandbox === '' && doc.html?.includes('Purchase order PO-117') && doc.html.includes('दर ₹ 2.50') && doc.html.includes('<table'), JSON.stringify(doc).slice(0, 200));
await preview('board-test.pdf');
const pdfFrame = await evaluate(`document.querySelector('section iframe:not([srcdoc])')?.getAttribute('src') ?? null`);
check('board preview: PDF in a frame from /view', /\/files\/\d+\/view$/.test(pdfFrame ?? ''), String(pdfFrame));
await preview('label.png');
check('board preview: picture shown', await evaluate(`!!document.querySelector('section img[src$="/view"]')`));
await preview('fake.pdf');
check('board preview: a fake PDF never runs as a page', !(await evaluate(`[...document.querySelectorAll('iframe')].some((f) => { try { return f.contentDocument?.querySelector('script'); } catch { return false; } })`)) && errors.length === 0, errors.join(' | '));
await clickText('Full screen');
await sleep(800);
const fullOn = await evaluate(`!!document.querySelector('section.fixed.inset-0')`);
await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
await sleep(800);
check('board preview: full screen opens and Esc closes it', fullOn && !(await evaluate(`!!document.querySelector('section.fixed.inset-0')`)));
// (Esc after a click INSIDE a PDF needs a real key press: Chrome leaves its own full screen then. Checked by hand, PR #46.)
await openTab('History');
pt = await text();
check('board History tab: who did what, newest first', /removed Gita from the board[\s\S]*added Gita to the board[\s\S]*created the board/.test(pt), pt.slice(-300));
await openTab('People');
pt = await text();
// The list itself (Gita was removed: she is only in the "Add someone…" picker now)
const people = (await evaluate(`[...document.querySelectorAll('li')].map((l) => l.innerText.replace(/\\s+/g, ' ').trim()).filter((t) => /Owner|Works on|Not on a step/.test(t))`)) ?? [];
check('board People tab: owner first, then the people', people.length === 3 && /Admin.*Owner/.test(people[0])
  && people.some((p) => p.includes('Esha')) && people.some((p) => p.includes('Farhan')) && !people.some((p) => p.includes('Gita')), JSON.stringify(people));
await openTab('Steps');
if ((await text()).includes('Lock plan')) await clickText('Lock plan');
check('owner locks the plan from the board', await waitFor('Plan locked · Unlock', 4000), errors.join(' | '));
await clickText('Edit plan');
check('locked: the owner can still open the plan editor', await waitFor('Edit the plan', 4000));

// Log in as Esha (a member; api_e2e.py changed her password): locked plan, her leave, phone width of the board
async function login(email, password, landing) {
  await send('Network.clearBrowserCookies');
  await open('/employee/login', 500);
  await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    const e = document.querySelector('input[type=email]'); const p = document.querySelector('input[type=password]');
    set.call(e, ${JSON.stringify(email)}); e.dispatchEvent(new Event('input', { bubbles: true }));
    set.call(p, ${JSON.stringify(password)}); p.dispatchEvent(new Event('input', { bubbles: true }));
    p.form.requestSubmit(); return true; })()`);
  return waitFor(landing, 10000);
}
check('Esha logs in', await login('esha@e2e.test', 'staff-pass-456', 'Good '));
await open('/employee/order-boards/E2E117-1', 2500);
pt = await text();
check('member: sees the lock and no "Edit plan"', /plan locked by the owner/i.test(pt) && !pt.includes('Edit plan'), pt.slice(0, 300));
// The attendance page's other views open from its "•••" Views menu
const view = async (label) => { await evaluate(`document.querySelector('button[title="Views"]')?.click()`); await sleep(300); await clickText(label); await sleep(1500); return text(); };
await open('/employee/attendance', 2500);
pt = await view('Leave Applications');
check('Esha\'s Leave Applications lists her approved leave', pt.includes('My Leave Applications') && /casual/i.test(pt) && /approved/i.test(pt), pt.slice(-300));
pt = await view('Shift Schedule');
check('Esha\'s Shift Schedule shows the shift the admin gave her', pt.includes('E2E Early') || pt.includes('E2EEARLY'), pt.slice(-300));
await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
const wide = () => evaluate('document.documentElement.scrollWidth > window.innerWidth + 1');
const phoneProblems = [];
await open('/employee/order-boards/E2E117-1', 2500);
for (const tab of ['Steps', 'Files', 'People', 'History']) {
  await openTab(tab);
  if (await wide()) phoneProblems.push(`${tab} tab scrolls sideways`);
}
await openTab('Files');
for (const name of ['rates-hindi.csv', 'plan.xlsx', 'po-117.docx', 'board-test.pdf']) {
  await preview(name);
  if (await wide()) phoneProblems.push(`${name} preview scrolls sideways`);
}
check('phone: board tabs and file previews fit 390 px', phoneProblems.length === 0 && errors.length === 0, [...phoneProblems, ...errors].join('; '));
await send('Emulation.clearDeviceMetricsOverride');

// Back to the admin: unlock the plan again (leave the data as it was)
check('admin logs in again', await login('admin@e2e.test', 'e2e-admin-pass-1', 'Live numbers'));
await open(BOARD, 2500);
await clickText('🔒 Plan locked · Unlock');
check('owner unlocks the plan', await waitFor('Lock plan', 4000));

// Phone width: menu button exists and opens the sidebar
await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 800, deviceScaleFactor: 2, mobile: true });
await open('/employee/tasks', 500);
await waitFor('Add task');
// The sidebar's groups start closed, so check where the sidebar is, not a link's text: off screen before, on screen after
const navLeft = () => evaluate('Math.round(document.querySelector("aside, nav")?.getBoundingClientRect().left ?? -9999)');
const before = await navLeft();
await evaluate(`document.querySelector('button[aria-label="Open menu"]').click()`);
await sleep(800);
const after = await navLeft();
check('phone: menu slides the sidebar onto the screen', before < 0 && after >= 0, `left before ${before}, after ${after}`);
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
