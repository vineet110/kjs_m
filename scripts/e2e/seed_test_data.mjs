// Fills the live site with realistic test data from the E2E test employees (Vineet 12 Nov: keep it; it is
// cleared before production). Everything is marked "E2E" so it is easy to find and remove later.
// Needs frontend/.auth/stress-users.json (scripts/e2e/create_test_employees.mjs).
// Run from the repo root:  node scripts/e2e/seed_test_data.mjs
//
// What it adds (from test employees only, never from real staff):
//   - attendance: 20 employees check in today, 12 of them check out again
//   - 12 internal leads, 24 tasks (to do / doing / done), 6 leave requests, 4 missed-punch requests
//   - a group chat "E2E Sales Team" (8 people) with a short conversation
// Test employees have no lead categories, so auto-assign never gives them real buyer records.
import { existsSync, readFileSync } from 'node:fs';

if (existsSync('frontend/.env.e2e.local')) process.loadEnvFile('frontend/.env.e2e.local');
const BASE = process.env.E2E_BASE_URL || 'https://kjs-m.vercel.app';
const USERS = JSON.parse(readFileSync('frontend/.auth/stress-users.json', 'utf8'));
const counts = {};
const problems = [];

async function session(u) {
  const r = await fetch(`${BASE}/api/v1/auth/login`, {
    method: 'POST', headers: { 'content-type': 'application/json', 'x-requested-with': 'kjs' },
    body: JSON.stringify({ email: u.email, password: u.password }),
  });
  if (!r.ok) throw new Error(`login ${u.email}: ${r.status}`);
  const cookie = r.headers.getSetCookie().map((c) => c.split(';')[0]).join('; ');
  return async (method, path, body) => {
    const res = await fetch(`${BASE}/api/v1${path}`, {
      method, headers: { cookie, 'content-type': 'application/json', 'x-requested-with': 'kjs' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) problems.push(`${u.email} ${method} ${path}: ${res.status} ${JSON.stringify(data).slice(0, 120)}`);
    else counts[`${method} ${path.replace(/\/\d+/g, '/:id')}`] = (counts[`${method} ${path.replace(/\/\d+/g, '/:id')}`] || 0) + 1;
    return data;
  };
}

const istDay = (offset) => new Date(Date.now() + 5.5 * 3600e3 + offset * 864e5).toISOString().slice(0, 10);
const pick = (list, i) => list[i % list.length];

const COMPANIES = ['Al Noor Trading LLC', 'Sunrise Foods Pvt Ltd', 'Bluebell Distributors', 'Green Valley Retail', 'Kaveri Imports', 'Desert Rose General Trading',
  'Spice Route Exports', 'Metro Mart Superstores', 'Himalaya Hospitality', 'Coastal Cafe Chain', 'Nile Star Foods', 'Gulf Pantry Co'];
const COUNTRIES = ['UAE', 'India', 'Saudi Arabia', 'Kenya', 'Oman', 'Qatar', 'Nigeria', 'Bangladesh'];
const BUYERS = ['Distributor', 'Importer', 'Retailer', 'Brand / private label', 'Other'];
const CATS = ['coffee', 'tea', 'health-drinks'];
const NEEDS = ['3-in-1 coffee sticks, 18 g', 'Private label instant tea premix', 'Malt drink powder in 500 g jars', 'Coffee premix for vending machines',
  'Cardamom tea premix sachets', 'Sugar-free coffee premix'];
const TASKS = ['Call back about samples', 'Send the price sheet', 'Share the product catalogue', 'Follow up on the quotation', 'Confirm the shipping terms',
  'Book a video call', 'Send spec sheets', 'Check the label artwork'];
const CHAT = ['Morning all, any update on the Al Noor samples?', 'Samples were dispatched yesterday, tracking shared on email.',
  'Great. Kaveri Imports wants a quote for 2 tonnes a month.', 'I will prepare it today, need the latest premix costs.',
  'Costs are in the shared sheet, updated last week.', 'Thanks! Also, Gulf Pantry asked for sugar-free options.',
  'We have two sugar-free blends, I will send the specs.', 'Reminder: trade fair stall planning at 4 pm.'];

const people = await Promise.all(USERS.slice(0, 24).map(async (u) => ({ ...u, call: await session(u) })));
console.log(`logged in ${people.length} test employees`);

// Attendance
for (const [i, p] of people.slice(0, 20).entries()) {
  await p.call('POST', '/attendance/check-in');
  if (i < 12) await p.call('POST', '/attendance/check-out', { notes: 'E2E test day' });
}

// Internal leads
for (let i = 0; i < 12; i++) {
  const p = people[i];
  await p.call('POST', '/employee/leads', {
    name: `E2E Buyer ${i + 1} (${pick(COMPANIES, i).split(' ')[0]})`, company: `${pick(COMPANIES, i)} (E2E)`,
    email: `e2e.buyer${i + 1}@kjs-e2e.test`, phone: `+971 50 ${String(1000000 + i * 7919).slice(-7)}`, country: pick(COUNTRIES, i),
    buyer_type: pick(BUYERS, i), category_slug: pick(CATS, i), quantity: `${(i % 4) + 1} tonnes a month`,
    message: `E2E test lead: ${pick(NEEDS, i)}. Asked for samples and a quote.`,
  });
}

// Tasks: to do, doing, done
for (let i = 0; i < 24; i++) {
  const p = people[i % 12];
  const due = new Date(Date.now() + ((i % 7) - 2) * 864e5).toISOString();
  const t = await p.call('POST', '/tasks', { title: `E2E ${pick(TASKS, i)} (${i + 1})`, notes: 'E2E test task', due_at: due, assignee_id: null });
  if (t?.id && i % 3 === 1) await p.call('PATCH', `/tasks/${t.id}`, { status: 'doing' });
  if (t?.id && i % 3 === 2) await p.call('PATCH', `/tasks/${t.id}`, { status: 'done', outcome: 'E2E: done, client informed' });
}

// Leave requests (future, different people, no overlaps per person)
const TYPES = ['casual', 'sick', 'earned', 'unpaid'];
for (let i = 0; i < 6; i++) {
  await people[12 + i].call('POST', '/attendance/leaves', {
    leave_type: pick(TYPES, i), start_date: istDay(20 + i * 2), end_date: istDay(21 + i * 2), is_half_day: false,
    reason: `E2E test leave (${pick(TYPES, i)})`,
  });
}

// Missed-punch requests (recent past weekdays)
for (let i = 0; i < 4; i++) {
  let back = -2 - i;
  if (new Date(istDay(back)).getUTCDay() === 0) back -= 1;
  await people[18 + i].call('POST', '/attendance/regularizations', { day: istDay(back), check_in: '09:40', check_out: '18:20', reason: 'E2E forgot to punch' });
}

// Group chat with a short conversation
const team = people.slice(0, 8);
const ch = await team[0].call('POST', '/chat/channels', { kind: 'group', name: 'E2E Sales Team', description: '', is_private: true, member_ids: team.slice(1).map((p) => p.id) });
if (ch?.id) for (const [i, line] of CHAT.entries()) await team[i % team.length].call('POST', `/chat/channels/${ch.id}/messages`, { body: line, mention_ids: [] });

console.log('added:', JSON.stringify(counts, null, 1));
console.log(problems.length ? `problems (${problems.length}):\n${problems.join('\n')}` : 'no problems');
