// KJS Chat with two people at once, in two real (headless) Chromes (two browsers = two separate logins).
// Asha and Ravi chat: a DM, live messages both ways without reloading, unread badges (list and sidebar),
// edit and delete seen live, a channel with an @mention picked from the list, a dropped connection that
// catches up (incl. a delete made while it was down), the phone layout, and no JS errors. Needs the e2e servers from README.md, with the chat settings in step 9 there. Adds two staff
// accounts (chat.asha@e2e.test, chat.ravi@e2e.test): run it on a fresh e2e database.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const WEB = process.argv[2] || 'http://localhost:3002';
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const ADMIN = { email: 'admin@e2e.test', password: 'e2e-admin-pass-1' }; // reset_e2e_db.sh
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;
const check = (name, ok, info = '') => { if (!ok) failed++; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok || !info ? '' : `  -> ${info}`}`); };

const chromes = [];
process.on('exit', () => {
  for (const c of chromes) {
    c.proc.kill();
    try { rmSync(c.profile, { recursive: true, force: true, maxRetries: 3 }); } catch { /* Chrome may still hold a file */ }
  }
});

/** One Chrome (its own profile = its own cookies) with one tab, driven over the DevTools protocol. */
async function browser(port) {
  const profile = mkdtempSync(join(tmpdir(), 'kjs-chat-e2e-'));
  const proc = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, '--no-first-run', '--window-size=1280,900', 'about:blank'], { stdio: 'ignore' });
  chromes.push({ proc, profile });
  for (let i = 0; i < 40; i++) { try { await fetch(`http://127.0.0.1:${port}/json/version`); break; } catch { await sleep(250); } }
  const t = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r));
  let id = 0;
  const pending = new Map();
  const b = { errors: [], loaded: 0 };
  b.send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  ws.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === 'Runtime.exceptionThrown') b.errors.push(m.params.exceptionDetails.exception?.description?.split('\n')[0] ?? m.params.exceptionDetails.text);
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') b.errors.push(`console.error: ${m.params.args.map((a) => a.value ?? a.description).join(' ').slice(0, 200)}`);
    if (m.method === 'Page.loadEventFired') b.loaded++;
  });
  await b.send('Runtime.enable');
  await b.send('Page.enable');
  b.eval = async (expr) => (await b.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
  b.open = async (path) => { const n = b.loaded; await b.send('Page.navigate', { url: WEB + path }); for (let i = 0; i < 120 && b.loaded === n; i++) await sleep(250); await sleep(1500); };
  /** Wait until the page says `text` (or, with not=true, no longer says it). */
  b.waitText = async (text, ms = 8000, not = false) => {
    for (let i = 0; i < ms / 200; i++) { if ((await b.eval(`document.body.innerText.includes(${JSON.stringify(text)})`)) !== not) return true; await sleep(200); }
    return false;
  };
  b.waitFor = async (expr, ms = 8000) => { for (let i = 0; i < ms / 200; i++) { if (await b.eval(expr)) return true; await sleep(200); } return false; };
  b.api = (path, method = 'GET', body) => b.eval(`fetch('/api/v1${path}', { method: ${JSON.stringify(method)}, headers: { 'content-type': 'application/json', 'x-requested-with': 'kjs' }${body ? `, body: JSON.stringify(${JSON.stringify(body)})` : ''} }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => null) }))`);
  b.click = (selectorExpr) => b.eval(`(() => { const el = ${selectorExpr}; if (!el) return false; el.click(); return true; })()`);
  b.button = (text) => b.click(`[...document.querySelectorAll('button')].find((x) => x.textContent.trim() === ${JSON.stringify(text)})`);
  b.type = async (text) => { await b.eval(`document.querySelector('textarea[aria-label="Message"]').focus()`); await b.send('Input.insertText', { text }); };
  b.key = async (key, code = key, vk) => {
    await b.send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: vk });
    await b.send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: vk });
  };
  b.enter = () => b.key('Enter', 'Enter', 13);
  b.sidebarChatBadge = () => b.eval(`(() => { const a = [...document.querySelectorAll('#portal-sidebar a')].find((x) => x.getAttribute('href')?.endsWith('/employee/chat')); return a ? a.textContent.replace('Chat', '').replace('unread', '').trim() : null; })()`);
  b.rowBadge = (title) => b.eval(`(() => { const r = [...document.querySelectorAll('aside button')].find((x) => x.textContent.includes(${JSON.stringify(title)})); return r ? (r.querySelector('.rounded-full')?.textContent.replace('unread', '').trim() ?? '') : null; })()`);
  return b;
}

const A = await browser(9411); // Asha
const B = await browser(9412); // Ravi
// Ravi's pages keep a handle on their chat connections, so the test can cut them on purpose and hold the
// reconnect (window.__hold = true: new connections go to a closed port and fail, so the page keeps retrying).
await B.send('Page.addScriptToEvaluateOnNewDocument', { source: `(() => {
  const Real = window.WebSocket; window.__socks = []; window.__hold = false;
  function Wrapped(url, protocols) {
    const ws = new Real(window.__hold ? 'ws://127.0.0.1:9/held' : url, protocols);
    window.__socks.push(ws);
    return ws;
  }
  Wrapped.prototype = Real.prototype;
  Object.assign(Wrapped, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
  window.WebSocket = Wrapped;
})()` });

// ---------- setup: the admin makes two staff accounts ----------
await A.open('/employee/login');
let r = await A.api('/auth/login', 'POST', ADMIN);
check('setup: admin logged in', r.status === 200, `status ${r.status}`);
const made = {};
for (const [key, name, phone] of [['asha', 'Asha', '+919800000101'], ['ravi', 'Ravi', '+919800000102']]) {
  r = await A.api('/admin/users', 'POST', { name, email: `chat.${key}@e2e.test`, phone, employee_code: `CH-${key}`, branch: 'Delhi', role: 'employee' });
  check(`setup: account for ${name}`, r.status === 201, `status ${r.status} ${JSON.stringify(r.body)?.slice(0, 120)} (run on a fresh e2e database)`);
  made[key] = { email: `chat.${key}@e2e.test`, password: r.body?.temp_password, id: r.body?.user?.id };
}
await A.api('/auth/logout', 'POST');
for (const [b, who] of [[A, 'asha'], [B, 'ravi']]) {
  if (b === B) await B.open('/employee/login');
  r = await b.api('/auth/login', 'POST', { email: made[who].email, password: made[who].password });
  check(`setup: ${who} logged in`, r.status === 200, `status ${r.status}`);
}

// ---------- both open the chat page ----------
await A.open('/employee/chat');
await B.open('/employee/chat');
check('both see the chat page', (await A.waitText('Pick a chat on the left')) && (await B.waitText('Pick a chat on the left')));
// The sidebar starts hidden: open it so its Chat entry can be read
for (const b of [A, B]) await b.click(`document.querySelector('button[aria-controls="portal-sidebar"]')`);
check('sidebar has a Chat entry', (await B.sidebarChatBadge()) !== null);
await sleep(1500); // the live connection opens

// ---------- Asha starts a DM with Ravi from the "+" dialog ----------
await A.click(`document.querySelector('button[aria-label="New chat or channel"]')`);
check('"+" opens the new chat dialog', await A.waitFor(`!!document.querySelector('[role="dialog"] input[aria-label="Find a colleague"]')`));
await A.waitText('Ravi');
await A.button('Ravi');
const PANE_TITLE = `document.querySelector('aside + section h2')?.textContent`;
check('picking Ravi opens the DM', await A.waitFor(`location.search.startsWith('?c=') && ${PANE_TITLE} === 'Ravi'`), await A.eval(PANE_TITLE));
const dmId = Number(await A.eval(`new URLSearchParams(location.search).get('c')`));

// ---------- Asha sends; Ravi sees it without reloading ----------
await A.type('Hello Ravi, the samples are ready');
await A.enter();
check('Asha: Enter sends (message shown, box empty)', (await A.waitText('Hello Ravi, the samples are ready')) && (await A.eval(`document.querySelector('textarea[aria-label="Message"]').value === ''`)));
check('Ravi: the DM appears in his list live', await B.waitText('Asha'));
const ROW_BADGE = (title) => `[...document.querySelectorAll('aside button')].find((x) => x.textContent.includes(${JSON.stringify(title)}))?.querySelector('.rounded-full')?.textContent.replace('unread', '').trim()`;
check('Ravi: unread badge 1 on the DM', await B.waitFor(`${ROW_BADGE('Asha')} === '1'`), `badge ${await B.rowBadge('Asha')}`);
check('Ravi: sidebar Chat badge shows 1', await B.waitFor(`[...document.querySelectorAll('#portal-sidebar a')].some((a) => a.getAttribute('href')?.endsWith('/employee/chat') && a.textContent.includes('1'))`), `badge ${await B.sidebarChatBadge()}`);

await B.click(`[...document.querySelectorAll('aside button')].find((x) => x.textContent.includes('Asha'))`);
check('Ravi: opening the DM shows the message', await B.waitText('Hello Ravi, the samples are ready'));
check('Ravi: unread badge cleared after reading', await B.waitFor(`![...document.querySelectorAll('aside button')].find((x) => x.textContent.includes('Asha'))?.querySelector('.rounded-full')`));
check('Ravi: sidebar badge cleared', await B.waitFor(`![...document.querySelectorAll('#portal-sidebar a')].find((a) => a.getAttribute('href')?.endsWith('/employee/chat'))?.querySelector('.rounded-full')`));

// ---------- Ravi replies; Asha sees it live; Shift+Enter makes a new line ----------
await B.type('Great, thanks!');
await B.enter(); // sends
await B.type('Second message'); // Shift+Enter must NOT send
await B.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, modifiers: 8 });
await B.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, modifiers: 8 });
check('Ravi: Shift+Enter keeps the text in the box (typed straight after sending)', (await B.eval(`document.querySelector('textarea[aria-label="Message"]').value.startsWith('Second message')`)) === true, JSON.stringify(await B.eval(`document.querySelector('textarea[aria-label="Message"]').value`)));
await B.eval(`(() => { const t = document.querySelector('textarea[aria-label="Message"]'); const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set; set.call(t, ''); t.dispatchEvent(new Event('input', { bubbles: true })); })()`);
check('Asha: sees Ravi\'s reply live', await A.waitText('Great, thanks!'));

// ---------- Asha edits and deletes; Ravi sees both live ----------
check('Asha: her own message has Edit and Delete', await A.eval(`[...document.querySelectorAll('button')].some((x) => x.textContent === 'Edit') && [...document.querySelectorAll('button')].some((x) => x.textContent === 'Delete')`));
const firstId = (await A.api(`/chat/channels/${dmId}/messages`)).body.messages[0].id;
await A.api(`/chat/messages/${firstId}`, 'PATCH', { body: 'Hello Ravi, the samples are packed' });
check('Ravi: sees the edit live, marked (edited)', (await B.waitText('the samples are packed')) && (await B.waitText('(edited)')));
await A.api(`/chat/messages/${firstId}`, 'DELETE');
check('Ravi: sees "Message deleted" live', await B.waitText('Message deleted'));

// ---------- a channel and an @mention picked from the list ----------
r = await A.api('/chat/channels', 'POST', { name: 'sales', description: 'Sales team', member_ids: [made.ravi.id] });
check('Asha: channel created', r.status === 201);
const salesId = r.body?.id;
check('Ravi: the new channel appears in his list live', await B.waitText('sales'));
await A.open(`/employee/chat?c=${salesId}`);
await A.type('@Ra');
check('Asha: typing @Ra shows Ravi in the picker', await A.waitFor(`!!document.querySelector('[role="listbox"]') && document.querySelector('[role="listbox"]').textContent.includes('@Ravi')`));
await A.enter(); // picks Ravi
await A.type('please check the price sheet');
check('Asha: the picker put "@Ravi " in the box', (await A.eval(`document.querySelector('textarea[aria-label="Message"]').value`)) === '@Ravi please check the price sheet');
await A.enter();
let bell = null;
for (let i = 0; i < 25 && bell?.body?.items?.[0]?.title !== 'Asha mentioned you in #sales'; i++) { await sleep(200); bell = await B.api('/employee/notifications'); }
check('Ravi: got a mention notification', bell?.body?.items?.[0]?.title === 'Asha mentioned you in #sales', JSON.stringify(bell?.body?.items?.[0]?.title));
await B.click(`[...document.querySelectorAll('aside button')].find((x) => x.textContent.includes('sales'))`);
check('Ravi: the mention is shown in bold', await B.waitFor(`[...document.querySelectorAll('strong')].some((s) => s.textContent === '@Ravi')`));
check('Ravi: a message he is mentioned in is highlighted', await B.waitFor(`!!document.querySelector('.bg-amber-50')`));

// ---------- plain text only: HTML is shown as typed, never run ----------
await A.type('<img src=x onerror="window.__xss=1">');
await A.enter();
check('Ravi: HTML in a message is shown as text, not run', (await B.waitText('<img src=x onerror')) && !(await B.eval('window.__xss === 1')));

// ---------- a dropped connection catches up (PR #55 review) ----------
r = await A.api(`/chat/channels/${salesId}/messages`, 'POST', { body: 'this one gets deleted while Ravi is offline' });
const doomed = r.body?.id;
check('Ravi: sees the message before the drop', await B.waitText('this one gets deleted while Ravi is offline'));
await B.eval(`window.__hold = true; window.__socks.forEach((w) => w.close())`);
check('Ravi: the page shows "Reconnecting…"', await B.waitText('Reconnecting'));
await A.api(`/chat/messages/${doomed}`, 'DELETE');
await A.api(`/chat/channels/${salesId}/messages`, 'POST', { body: 'sent while Ravi was offline' });
await sleep(1500);
check('Ravi: while offline, the delete has not reached him (its live event is lost)', await B.waitText('this one gets deleted while Ravi is offline', 500));
await B.eval(`window.__hold = false`);
check('Ravi: after reconnecting, the message sent meanwhile shows', await B.waitText('sent while Ravi was offline', 20000));
check('Ravi: after reconnecting, the delete made meanwhile shows', await B.waitText('this one gets deleted while Ravi is offline', 5000, true));
check('Ravi: the "Reconnecting…" bar is gone', await B.waitText('Reconnecting', 5000, true));

// ---------- phone layout ----------
await B.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 800, deviceScaleFactor: 3, mobile: true });
await B.open('/employee/chat');
check('phone: the chat list fills the screen', await B.waitFor(`getComputedStyle(document.querySelector('aside.w-full')).display !== 'none' && document.querySelector('aside + section').offsetWidth === 0`));
await B.click(`[...document.querySelectorAll('aside button')].find((x) => x.textContent.includes('sales'))`);
check('phone: a chat opens full screen with a back button', await B.waitFor(`!!document.querySelector('button[aria-label="Back to chats"]') && getComputedStyle(document.querySelector('aside.w-full')).display === 'none'`));
await B.click(`document.querySelector('button[aria-label="Back to chats"]')`);
check('phone: back returns to the list', await B.waitFor(`!location.search && getComputedStyle(document.querySelector('aside.w-full')).display !== 'none'`));
check('phone: no sideways scrolling', !(await B.eval('document.documentElement.scrollWidth > innerWidth')));

// ---------- no JS errors ----------
check('Asha: no JS errors', A.errors.length === 0, A.errors.join(' | '));
check('Ravi: no JS errors', B.errors.length === 0, B.errors.join(' | '));

console.log(failed ? `\n${failed} FAILED` : '\nALL PASSED');
process.exit(failed ? 1 : 0);
