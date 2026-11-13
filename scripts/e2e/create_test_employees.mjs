// Creates test employees on the live site (kept on purpose, Vineet 12 Nov) through the admin API.
// Emails e2e.emp001@kjs-e2e.test ... ; branch "E2E Branch"; role employee; active.
// Their one-time passwords go to e2e-output/auth/stress-users.json (git-ignored), for the stress test.
// Run from the repo root:  node scripts/e2e/create_test_employees.mjs [count=75]
// Safe to run again: existing emails are skipped (their passwords stay in the file from the first run).
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const ENV = 'frontend/.env.e2e.local';
if (existsSync(ENV)) process.loadEnvFile(ENV);
const BASE = process.env.E2E_BASE_URL || 'https://kjs-m.vercel.app';
const COUNT = Number(process.argv[2] || 75);
const OUT = 'e2e-output/auth/stress-users.json';

const FIRST = ['Aarav', 'Priya', 'Rohan', 'Ananya', 'Vikram', 'Sneha', 'Arjun', 'Kavya', 'Rahul', 'Meera', 'Aditya', 'Pooja', 'Karan', 'Divya', 'Siddharth'];
const LAST = ['Sharma', 'Patel', 'Iyer', 'Reddy', 'Gupta'];

async function login(email, password) {
  const r = await fetch(`${BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-requested-with': 'kjs' },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error(`Admin login failed: ${r.status} ${await r.text()}`);
  return r.headers.getSetCookie().map((c) => c.split(';')[0]).join('; ');
}

const cookie = await login(process.env.E2E_EMAIL_A, process.env.E2E_PASSWORD_A);
const api = (path, init = {}) =>
  fetch(`${BASE}/api/v1${path}`, { ...init, headers: { cookie, 'content-type': 'application/json', 'x-requested-with': 'kjs', ...init.headers } });

const saved = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : [];
const known = new Set((await (await api('/admin/users')).json()).map((u) => u.email));
let made = 0, skipped = 0;
const failed = [];

for (let i = 1; i <= COUNT; i++) {
  const n = String(i).padStart(3, '0');
  const email = `e2e.emp${n}@kjs-e2e.test`;
  if (known.has(email)) { skipped++; continue; }
  const name = `${FIRST[(i - 1) % FIRST.length]} ${LAST[Math.floor((i - 1) / FIRST.length) % LAST.length]} E2E${n}`;
  const phone = `+91 98765 ${String(10000 + i).slice(-5)}`;
  const body = { name, email, phone, employee_code: `E2E-EMP-${n}`, branch: 'E2E Branch', role: 'employee', reporting_to: null };
  const r = await api('/admin/users', { method: 'POST', body: JSON.stringify(body) });
  if (r.ok) {
    const { user, temp_password } = await r.json();
    saved.push({ id: user.id, name, email, password: temp_password });
    made++;
  } else failed.push(`${email}: ${r.status} ${(await r.text()).slice(0, 120)}`);
}

mkdirSync('e2e-output/auth', { recursive: true });
writeFileSync(OUT, JSON.stringify(saved, null, 2));
console.log(`created ${made}, already there ${skipped}, failed ${failed.length}; ${saved.length} logins in ${OUT}`);
if (failed.length) console.log(failed.join('\n'));
