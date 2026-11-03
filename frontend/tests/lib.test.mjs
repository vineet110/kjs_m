// Unit tests for small helpers in src/lib, with Node's built-in test runner (no extra package):
//   npm test        (from frontend/)
// Each TypeScript file is compiled on the fly with the project's own TypeScript, then imported.
// SRC_DIR=<folder> runs the same tests on another copy of src/lib (e.g. old code, to see them fail).
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';

const SRC = process.env.SRC_DIR || fileURLToPath(new URL('../src/lib/', import.meta.url));
const OUT = mkdtempSync(join(tmpdir(), 'kjs-lib-test-'));
after(() => rmSync(OUT, { recursive: true, force: true }));
const ORIGIN = 'http://localhost:3002';

/** Compiles src/lib/<name>.ts (with its imports replaced by `stubs`) and imports it. */
async function load(name, stubs = '', before = '') {
  // Every import (one line or several) is removed; `stubs` (added after) and `before` (added first, for what
  // the file uses as soon as it loads) define what the file needs instead
  const source = before + '\n' + readFileSync(join(SRC, `${name}.ts`), 'utf8').replace(/^import\b[\s\S]*?from\s*['"][^'"]+['"];?/gm, '') + '\n' + stubs;
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  const file = join(OUT, `${name}.mjs`);
  writeFileSync(file, js);
  return import(pathToFileURL(file).href);
}

// ---------- safeNext: where to go after login ----------
globalThis.window = { location: { origin: ORIGIN } };
const { safeNext } = await load('safe-url');

test('safeNext keeps a normal page on our site', () => {
  assert.equal(safeNext('/admin/leads?status=new#top'), '/admin/leads?status=new#top');
  assert.equal(safeNext('/employee/tasks'), '/employee/tasks');
});

test('safeNext refuses other websites (open redirect)', () => {
  for (const evil of ['https://evil.com', '//evil.com', '/\\evil.com', 'evil.com', 'javascript:alert(1)']) {
    assert.equal(safeNext(evil), null, evil);
  }
});

test('safeNext refuses paths that become "//evil.com" once cleaned up (PR #12 review)', () => {
  for (const evil of ['/..//evil.com', '/.//evil.com', '/%2e%2e//evil.com', '/a/..//evil.com']) {
    assert.equal(safeNext(evil), null, evil);
  }
});

test('safeNext never leads back to the login page (repeated slashes, encoded letters too)', () => {
  for (const login of ['/employee/login', '/employee/login/', '/en/employee/login', '/employee//login', '//employee/login', '/employee/%6Cogin', '/employee/logi%6E']) {
    assert.equal(safeNext(login), null, login);
  }
});

// ---------- api(): every answer is either the data or an ApiFailure ----------
const { api, upload, ApiFailure } = await load('api', "const newRequestId = () => 'test-request-id'; const log = () => {};");
const answer = (body, status = 200, type = 'application/json') => async () => new Response(body, { status, headers: { 'content-type': type } });

test('api returns readable JSON data', async () => {
  globalThis.fetch = answer('{"id":7,"name":"Asha"}');
  assert.deepEqual(await api('/auth/me'), { id: 7, name: 'Asha' });
});

test('api: a 204 (no content) is fine', async () => {
  globalThis.fetch = async () => new Response(null, { status: 204 });
  assert.equal(await api('/auth/logout', { method: 'POST' }), undefined);
});

test('api: a "success" (200) we cannot read is an error, never {} (PR #12 review)', async () => {
  globalThis.fetch = answer('<html>proxy page</html>', 200, 'text/html');
  await assert.rejects(api('/auth/me'), (err) => err instanceof ApiFailure && err.status === 200 && err.body.code === 'bad_response' && err.body.request_id === 'test-request-id');
});

test('upload: a "success" we cannot read is an error too (same rules as api)', async () => {
  globalThis.fetch = answer('<html>proxy page</html>', 200, 'text/html');
  await assert.rejects(upload('/files', new FormData()), (err) => err instanceof ApiFailure && err.body.code === 'bad_response');
  globalThis.fetch = answer('Bad gateway', 502, 'text/html');
  await assert.rejects(upload('/files', new FormData()), (err) => err.status === 502 && err.body.request_id === 'test-request-id');
});

test('api: a connection cut while a 200 is read is an error', async () => {
  const cut = new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode('{"id":')); c.error(new TypeError('network')); } });
  globalThis.fetch = async () => new Response(cut, { status: 200, headers: { 'content-type': 'application/json' } });
  await assert.rejects(api('/auth/me'), (err) => err instanceof ApiFailure && err.body.code === 'bad_response');
});

test('api: an error page that is not JSON keeps its status, with the request id', async () => {
  globalThis.fetch = answer('Bad gateway', 502, 'text/html');
  await assert.rejects(api('/auth/me'), (err) => err instanceof ApiFailure && err.status === 502 && err.body.request_id === 'test-request-id');
});

test('api: a JSON error keeps the server message and request id', async () => {
  globalThis.fetch = answer('{"code":"forbidden","message":"Not allowed.","details":{},"request_id":"srv-1"}', 403);
  await assert.rejects(api('/x'), (err) => err.status === 403 && err.message === 'Not allowed.' && err.body.request_id === 'srv-1');
});

test('api: a server that never answers ends as a time-out (timeoutMs)', async () => {
  globalThis.fetch = (_url, init) => new Promise((_resolve, reject) => init.signal.addEventListener('abort', () => reject(init.signal.reason)));
  // AbortSignal.timeout's timer doesn't keep Node running (a page in a browser does): with nothing else to
  // do, Node would stop before it fires and cancel this test (seen in CI on Node 22). Keep Node running.
  const keepAlive = setTimeout(() => {}, 5_000);
  try {
    await assert.rejects(api('/auth/me', { timeoutMs: 50 }), (err) => err instanceof ApiFailure && err.status === 0 && err.body.code === 'timeout');
  } finally {
    clearTimeout(keepAlive);
  }
});

// ---------- partner types: "broker" is shown as "Referral partner" (UI step 4) ----------
const { PARTNER_TYPES, partnerLabel } = await load('partners');

test('partnerLabel shows "Referral partner" for the saved value "broker"', () => {
  assert.equal(partnerLabel('broker'), 'Referral partner');
  assert.equal(partnerLabel('forwarder'), 'Freight forwarder');
});

test('partnerLabel shows an unknown saved value as it is (never blank)', () => {
  assert.equal(partnerLabel('reseller'), 'reseller');
});

test('partner labels are the same here and in the backend (content_service.PARTNER_LABELS)', () => {
  const py = readFileSync(fileURLToPath(new URL('../../backend/app/services/content_service.py', import.meta.url)), 'utf8');
  const dict = py.match(/PARTNER_LABELS = \{([\s\S]*?)\}/)?.[1] ?? '';
  const backend = Object.fromEntries([...dict.matchAll(/"(\w+)": "([^"]+)"/g)].map((m) => [m[1], m[2]]));
  assert.deepEqual(backend, Object.fromEntries(PARTNER_TYPES));
});

test('partner types keep the values the API accepts, and no label says "Broker"', () => {
  assert.deepEqual(PARTNER_TYPES.map(([value]) => value), ['agent', 'broker', 'forwarder', 'distributor', 'other']);
  assert.ok(PARTNER_TYPES.every(([, label]) => !/broker/i.test(label)));
});

// ---------- recommend(): best sellers left out of Recommended, but still count as the visitor's interest ----------
const { recommend } = await load('history', 'const useSyncExternalStore = () => {};');
const product = (slug, categorySlug) => ({ slug, name: slug, categorySlug, categoryName: categorySlug, image: `/${slug}.jpg`, summary: '', packFormats: '', moq: '', privateLabel: true, items: [] });
const CATALOGUE = [
  product('best-coffee', 'coffee'), product('coffee-2', 'coffee'), product('coffee-3', 'coffee'),
  product('tea-1', 'tea'), product('tea-2', 'tea'), product('wafer-1', 'wafers'), product('wafer-2', 'wafers'),
];

test('recommend: a visitor who only opened a best seller still gets "Recommended for you" from its category', () => {
  const picks = recommend(CATALOGUE, ['best-coffee'], [], 2, ['best-coffee']);
  assert.equal(picks.reason, 'viewed');
  assert.deepEqual(picks.products.map((p) => p.slug).sort(), ['coffee-2', 'coffee-3']);
});

test('recommend: excluded products are never shown, even to fill up the row', () => {
  const picks = recommend(CATALOGUE, ['best-coffee'], [], 10, ['best-coffee']);
  assert.ok(!picks.products.some((p) => p.slug === 'best-coffee'));
  assert.equal(picks.products.length, CATALOGUE.length - 1);
});

// ---------- offer badge (UI step 6): "Up to X% OFF", only when staff set an offer ----------
const catalogueLib = await load('catalogue');
const { offerLabel, toHomeProduct } = catalogueLib;

test('offerLabel: "Up to X% OFF" for a set offer, nothing otherwise', () => {
  assert.equal(offerLabel(20), 'Up to 20% OFF');
  for (const none of [null, undefined, 0]) assert.equal(offerLabel(none), null, String(none));
});

test('toHomeProduct keeps the offer for the home cards', () => {
  const api = { slug: 'x', name: 'X', description: '', pack_formats: '', moq: '', image_path: '', private_label: true, is_best_seller: false, category_slug: 'c', category_name: 'C', offer_percent: 15 };
  assert.equal(toHomeProduct(api).offerPercent, 15);
  assert.equal(toHomeProduct({ ...api, offer_percent: null }).offerPercent, null);
});

// ---------- phone code and country pickers (UI step 7) ----------
const countriesData = readFileSync(join(SRC, 'countries-data.ts'), 'utf8').replace('export const', 'const');
const countriesLib = await load('countries', '', countriesData);
const { filterCountries, composePhone, splitPhone, phoneLooksValid, countryByName, COUNTRIES } = countriesLib;
const names = (list) => list.map((c) => c.name);

test('countries: every country / region once, with a phone code', () => {
  assert.ok(COUNTRIES.length > 240);
  assert.equal(new Set(COUNTRIES.map((c) => c.code)).size, COUNTRIES.length);
  assert.ok(COUNTRIES.every((c) => /^[A-Z]{2}$/.test(c.code) && /^\d{1,4}$/.test(c.dial) && c.name));
});

test('picker search: a letter shows the countries starting with it', () => {
  const a = filterCountries('a');
  // Accents don't count (Åland Islands is an A); later words don't count for one letter
  assert.ok(a.length > 5 && a.every((c) => c.name.normalize('NFD').toLowerCase().startsWith('a')), names(a).join());
  assert.ok(names(filterCountries('ind')).includes('India'));
  assert.ok(names(filterCountries('emirates')).includes('United Arab Emirates')); // a later word too
});

test('picker search: a digit (with or without +) shows the codes starting with it', () => {
  const nine = filterCountries('9');
  assert.ok(nine.length > 5 && nine.every((c) => c.dial.startsWith('9')));
  assert.ok(names(filterCountries('+91')).includes('India'));
  assert.ok(names(filterCountries('97')).includes('United Arab Emirates'));
  assert.equal(filterCountries('').length, COUNTRIES.length);
});

test('composePhone saves "+code number"; an empty number saves nothing', () => {
  assert.equal(composePhone('91', ' 98765 43210 '), '+91 98765 43210');
  assert.equal(composePhone('91', '   '), '');
});

test('splitPhone reads a saved phone back (main country for shared codes)', () => {
  assert.deepEqual(splitPhone('+971 50 123 4567'), { code: 'AE', number: '50 123 4567' });
  assert.deepEqual(splitPhone('+1 415 555 0100'), { code: 'US', number: '415 555 0100' });
  assert.deepEqual(splitPhone('+1 416 555 0100', 'CA'), { code: 'CA', number: '416 555 0100' }); // keeps the picked one
  assert.deepEqual(splitPhone('98765 43210'), { code: 'IN', number: '98765 43210' }); // old numbers without a code
  assert.deepEqual(splitPhone(''), { code: 'IN', number: '' });
  // Saved without a space after the code: the code is found, the number keeps its own digits (review)
  assert.deepEqual(splitPhone('+919876543210'), { code: 'IN', number: '9876543210' });
  assert.deepEqual(splitPhone('+971501234567'), { code: 'AE', number: '501234567' });
});

test('phoneLooksValid: digits and spaces, 6 to 15 digits counting the code, like the server (empty is fine)', () => {
  for (const ok of ['', '98765 43210', '50-123-4567', '(020) 7946 0958']) assert.ok(phoneLooksValid(ok, '91'), ok);
  for (const bad of ['abc123', '123', '98765x43210']) assert.ok(!phoneLooksValid(bad, '91'), bad);
  // 13 digits: fine with +91 (15 in all), too long with +971 (16 in all), as the server counts (review)
  assert.ok(phoneLooksValid('1234567890123', '91'));
  assert.ok(!phoneLooksValid('1234567890123', '971'));
});

test('countryByName finds a saved country (the country field stores the name)', () => {
  assert.equal(countryByName('United Arab Emirates')?.code, 'AE');
  assert.equal(countryByName('Atlantis'), undefined);
});

test('savedPhoneOk: a remembered phone passes the same rule as the server, or must be typed again (PR #16 review)', () => {
  const { savedPhoneOk } = countriesLib;
  for (const ok of ['', '+91 98765 43210', '9876543210', '+44 (020) 7946 0958']) assert.ok(savedPhoneOk(ok), ok);
  for (const bad of ['call me after 6', '12345', '+1 2345 6789 0123 4567']) assert.ok(!savedPhoneOk(bad), bad);
});

test('country names are stored right, accents included (no garbled text), and are found by search', () => {
  assert.ok(!COUNTRIES.some((c) => /Ã|â€/.test(c.name)), COUNTRIES.filter((c) => /Ã|â€/.test(c.name)).map((c) => c.name).join());
  assert.ok(names(filterCountries('türk')).includes('Türkiye'));
  assert.ok(names(filterCountries('reunion')).includes('Réunion'));
});
