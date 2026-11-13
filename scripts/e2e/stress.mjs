// Stress test of the live site with the test employees (e2e-output/auth/stress-users.json).
// Each virtual user logs in once, then opens a random employee page every 2-4 s (the same API calls the
// page makes, sent together like a browser does). Steps: 10, 25, 50 users, 2 minutes each.
// Read-only: no check-in, no messages, nothing saved. Stops itself if the site is clearly overloaded:
// more than 20% errors, or p95 above 10 s, over the last 30 s.
// Run from the repo root:  node scripts/e2e/stress.mjs   ->  e2e-output/stress/stress.json
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const ENV = 'frontend/.env.e2e.local';
if (existsSync(ENV)) process.loadEnvFile(ENV);
const BASE = process.env.E2E_BASE_URL || 'https://kjs-m.vercel.app';
const USERS = JSON.parse(readFileSync('e2e-output/auth/stress-users.json', 'utf8'));
const STAGES = (process.env.STRESS_STAGES || '10,25,50').split(',').map(Number);
const STAGE_MS = Number(process.env.STRESS_STAGE_SECONDS || 120) * 1000;
const TIMEOUT_MS = 30_000;
const OUT = 'e2e-output/stress/stress.json'; // not results/: Playwright empties that folder on every run

// Employee pages and the API calls each one makes when it opens
const PAGES = {
  'Today': ['/auth/me', '/tasks/stats', '/employee/colleagues', '/chat/unread'],
  'Leads': ['/auth/me', '/employee/contacts', '/employee/colleagues'],
  'Tasks & Track': ['/auth/me', '/tasks', '/employee/colleagues'],
  'My attendance': ['/auth/me', '/attendance/today', '/attendance/holidays', '/attendance/leaves', '/attendance/regularizations', '/attendance/shifts'],
  'My batches': ['/auth/me', '/assign/my-batches'],
  'My order boards': ['/auth/me', '/boards'],
  'Chat': ['/auth/me', '/chat/channels', '/chat/unread'],
  'Profile': ['/auth/me', '/employee/colleagues'],
};
const PAGE_NAMES = Object.keys(PAGES);

const samples = []; // { t, stage, kind: 'api'|'login'|'page', name, ms, ok, status }
let stage = 0;
let stop = false;
let stopReason = '';

async function timed(kind, name, fn) {
  const t0 = performance.now();
  let ok = false, status = 0;
  try {
    const r = await fn();
    status = r.status;
    ok = r.ok;
    await r.arrayBuffer(); // read the whole answer, like a browser
  } catch (e) {
    status = e.name === 'TimeoutError' ? 'timeout' : 'network';
  }
  const ms = performance.now() - t0;
  samples.push({ t: Date.now(), stage, kind, name, ms, ok, status });
  return { ok, ms };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const signal = () => AbortSignal.timeout(TIMEOUT_MS);

async function virtualUser(u, until) {
  let cookie = '';
  const res = await timed('login', 'POST /auth/login', async () => {
    const r = await fetch(`${BASE}/api/v1/auth/login`, {
      method: 'POST', signal: signal(),
      headers: { 'content-type': 'application/json', 'x-requested-with': 'kjs' },
      body: JSON.stringify({ email: u.email, password: u.password }),
    });
    cookie = r.headers.getSetCookie().map((c) => c.split(';')[0]).join('; ');
    return r;
  });
  if (!res.ok) return;
  while (!stop && Date.now() < until()) {
    const page = PAGE_NAMES[Math.floor(Math.random() * PAGE_NAMES.length)];
    const t0 = performance.now();
    const all = await Promise.all(PAGES[page].map((p) =>
      timed('api', `GET ${p}`, () => fetch(`${BASE}/api/v1${p}`, { signal: signal(), headers: { cookie, 'x-requested-with': 'kjs' } }))));
    samples.push({ t: Date.now(), stage, kind: 'page', name: page, ms: performance.now() - t0, ok: all.every((x) => x.ok), status: 0 });
    await sleep(2000 + Math.random() * 2000);
  }
}

function pct(list, p) {
  if (!list.length) return 0;
  const s = [...list].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.ceil((p / 100) * s.length) - 1)];
}
function stats(list) {
  const ms = list.map((x) => x.ms);
  const errors = list.filter((x) => !x.ok).length;
  return { requests: list.length, errors, error_rate: list.length ? errors / list.length : 0,
    p50: Math.round(pct(ms, 50)), p95: Math.round(pct(ms, 95)), max: Math.round(Math.max(0, ...ms)) };
}

// Safety stop: checked every 5 s over the last 30 s of API calls
const watchdog = setInterval(() => {
  const recent = samples.filter((x) => x.kind === 'api' && x.t > Date.now() - 30_000);
  if (recent.length < 30) return;
  const s = stats(recent);
  process.stdout.write(`  [${STAGES[stage - 1] ?? 0} users] last 30 s: ${s.requests} calls, p95 ${s.p95} ms, errors ${(s.error_rate * 100).toFixed(1)}%\n`);
  if (s.error_rate > 0.2 || s.p95 > 10_000) {
    stop = true;
    stopReason = `Safety stop at ${STAGES[stage - 1]} users: last 30 s p95 ${s.p95} ms, errors ${(s.error_rate * 100).toFixed(1)}%`;
  }
}, 5000);

// Wake the server first (Render's free plan sleeps)
const wake = await timed('warmup', 'GET /api/health', () => fetch(`${BASE}/api/health`, { signal: AbortSignal.timeout(75_000) }));
console.log(`warm-up: health ${wake.ok ? 'ok' : 'FAILED'} in ${Math.round(wake.ms)} ms`);
if (!wake.ok) process.exit(1);

const started = new Date().toISOString();
const running = [];
const stageInfo = [];
let end = 0;
for (let i = 0; i < STAGES.length && !stop; i++) {
  stage = i + 1;
  const t0 = Date.now();
  end = t0 + STAGE_MS;
  const want = Math.min(STAGES[i], USERS.length);
  console.log(`stage ${stage}: ${want} users for ${STAGE_MS / 1000} s`);
  // New users join spread over 10 s (not all logging in at the same instant)
  const joining = want - running.length;
  for (let k = running.length; k < want; k++) {
    running.push(virtualUser(USERS[k], () => end));
    await sleep(10_000 / Math.max(1, joining));
  }
  while (!stop && Date.now() < end) await sleep(500);
  stageInfo.push({ stage, users: want, seconds: Math.round((Date.now() - t0) / 1000) });
}
end = 0; // everyone finishes their current page and stops
await Promise.all(running);
clearInterval(watchdog);

// ---------- Report ----------
const api = samples.filter((x) => x.kind === 'api');
const report = {
  site: BASE, started, finished: new Date().toISOString(), stopped_early: stop, stop_reason: stopReason,
  pass_rule: 'p95 under 2000 ms and errors under 1% at every step',
  stages: stageInfo.map((s) => {
    const mine = api.filter((x) => x.stage === s.stage);
    const st = stats(mine);
    return { ...s, ...st, rps: +(st.requests / Math.max(1, s.seconds)).toFixed(1),
      logins: stats(samples.filter((x) => x.kind === 'login' && x.stage === s.stage)),
      pass: st.p95 < 2000 && st.error_rate < 0.01 };
  }),
  endpoints: [...new Set(api.map((x) => x.name))].map((name) => ({ name, ...stats(api.filter((x) => x.name === name)) })).sort((a, b) => b.p95 - a.p95),
  pages: PAGE_NAMES.map((name) => ({ name, ...stats(samples.filter((x) => x.kind === 'page' && x.name === name)) })),
  error_kinds: Object.entries(api.filter((x) => !x.ok).reduce((m, x) => ({ ...m, [`${x.name} -> ${x.status}`]: (m[`${x.name} -> ${x.status}`] || 0) + 1 }), {}))
    .map(([what, count]) => ({ what, count })).sort((a, b) => b.count - a.count),
};
mkdirSync('e2e-output/stress', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report.stages, null, 1));
console.log(stop ? stopReason : 'Finished all steps.');
console.log(`Report: ${OUT}`);
