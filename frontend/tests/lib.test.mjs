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
async function load(name, stubs = '') {
  // Every import (one line or several) is removed; `stubs` defines what the file needs instead
  const source = readFileSync(join(SRC, `${name}.ts`), 'utf8').replace(/^import\b[\s\S]*?from\s*['"][^'"]+['"];?/gm, '') + '\n' + stubs;
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

test('productPayload (Admin > Products, Hide/Show): sends every field back, so hiding never clears the offer', () => {
  const { productPayload } = catalogueLib;
  const row = { id: 3, slug: 'x', name: 'X', description: 'd', pack_formats: 'p', moq: 'm', image_path: '/i.jpg', private_label: false, is_best_seller: true, category_slug: 'c', category_name: 'C', offer_percent: 25, is_active: true };
  assert.deepEqual(productPayload(row), { category_slug: 'c', name: 'X', description: 'd', pack_formats: 'p', moq: 'm', image_path: '/i.jpg', private_label: false, is_best_seller: true, offer_percent: 25 });
});
