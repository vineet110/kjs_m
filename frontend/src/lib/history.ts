// What a visitor did on the site, kept in THIS browser only (localStorage), never sent to us:
// products they opened, and their enquiry list. Used for "Recommended for you" on the home page.
// If the browser blocks storage (private window, strict settings) or it is full, everything still
// works for the visit: what can't be saved is kept in memory until the page is closed.
import { useSyncExternalStore } from 'react';
import type { HomeProduct } from './catalogue';

const LIST_KEY = 'kjs_enquiry_list'; // the enquiry list (ProductExplorer)
const VIEWED_KEY = 'kjs_viewed';
const VIEWED_MAX = 12;
/** Fired on window when the history or the enquiry list changes in this tab. */
export const HISTORY_EVENT = 'kjs:history';

// ---------- storage, with an in-memory fallback per key ----------
// A value that could not be saved (storage blocked, or full) is kept in memory and wins over storage
// for that key only; every other key is still read from storage (a full store is still readable).
const memory = new Map<string, string>();

function getRaw(key: string): string | null {
  if (memory.has(key)) return memory.get(key)!;
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // blocked: nothing saved yet for this key in this visit
  }
}

function setRaw(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
    memory.delete(key); // saved: storage is the truth again for this key
  } catch {
    memory.set(key, value); // blocked or full: keep it for this visit
  }
}

function read(key: string): string[] {
  try {
    const v = JSON.parse(getRaw(key) || '[]');
    return Array.isArray(v) ? v.filter((s): s is string => typeof s === 'string') : [];
  } catch {
    return [];
  }
}

// Saves, and tells listeners, only when something really changed (no needless work on every load)
function write(key: string, list: string[]) {
  const next = JSON.stringify(list);
  if (getRaw(key) === next) return;
  setRaw(key, next);
  cached = null;
  window.dispatchEvent(new Event(HISTORY_EVENT));
}

/** Products this visitor opened, most recent first. */
export function readViewed(): string[] {
  return read(VIEWED_KEY);
}

export function readEnquiryList(): string[] {
  return read(LIST_KEY);
}

export function saveEnquiryList(list: string[]) {
  write(LIST_KEY, list);
}

/** Remember that this visitor opened a product (product page or quick view). */
export function rememberViewed(slug: string) {
  write(VIEWED_KEY, [slug, ...readViewed().filter((s) => s !== slug)].slice(0, VIEWED_MAX));
}

// ---------- useHistory: one shared, live view of the history ----------
export type History = { viewed: string[]; listed: string[]; ready: boolean };
const SERVER: History = { viewed: [], listed: [], ready: false }; // server render and hydration
let cached: History | null = null; // what getSnapshot returns until something changes
let last: History | null = null; // the previous snapshot, reused when the content is the same

// React calls this on every render: it reads storage only after a change cleared the cache
function current(): History {
  if (cached) return cached;
  const next: History = { viewed: readViewed(), listed: readEnquiryList(), ready: true };
  // Same content: keep the same object, so React doesn't re-render for nothing
  const same = last && last.viewed.join() === next.viewed.join() && last.listed.join() === next.listed.join();
  cached = same ? last! : next;
  last = cached;
  return cached;
}

function subscribe(onChange: () => void) {
  const changed = () => {
    cached = null;
    onChange();
  };
  const fromOtherTab = (e: StorageEvent) => {
    if (e.key === null || e.key === LIST_KEY || e.key === VIEWED_KEY) changed();
  };
  window.addEventListener(HISTORY_EVENT, changed);
  window.addEventListener('storage', fromOtherTab); // another tab changed it
  window.addEventListener('pageshow', changed); // back/forward cache restore
  return () => {
    window.removeEventListener(HISTORY_EVENT, changed);
    window.removeEventListener('storage', fromOtherTab);
    window.removeEventListener('pageshow', changed);
  };
}

/**
 * The visitor's history, kept up to date with changes in this tab AND in other tabs. Shared by the
 * enquiry list and the recommendations, so a tab never saves an old list over a newer one.
 * `ready` is false on the server and during hydration (nothing is read from the browser yet).
 */
export function useHistory(): History {
  return useSyncExternalStore(subscribe, current, () => SERVER);
}

// ---------- recommendations ----------
/** A mix across categories: the first product of each category, then the second of each, and so on. */
export function mixAcrossCategories(products: HomeProduct[], count: number): HomeProduct[] {
  const byCat = new Map<string, HomeProduct[]>();
  for (const p of products) {
    const list = byCat.get(p.categorySlug);
    if (list) list.push(p);
    else byCat.set(p.categorySlug, [p]);
  }
  const out: HomeProduct[] = [];
  for (let round = 0; out.length < count; round++) {
    const row = [...byCat.values()].map((list) => list[round]).filter((p): p is HomeProduct => !!p);
    if (!row.length) break;
    out.push(...row);
  }
  return out.slice(0, count);
}

/** Why the picks are personal: what the visitor viewed, their enquiry list, both, or nothing (a mix). */
export type Reason = 'viewed' | 'listed' | 'both' | null;

/**
 * Recommendations: products from the categories the visitor looked at (recent views count most, the
 * enquiry list counts too), leaving out what they already opened or listed; topped up with a mix
 * across categories, and (only if needed) with products they already saw, so there are always `count`
 * picks when the catalogue has that many (the section never changes size). With no history it is
 * just the mix. The reason says what really produced the personal picks.
 */
export function recommend(products: HomeProduct[], viewed: string[], listed: string[], count: number): { products: HomeProduct[]; reason: Reason } {
  const bySlug = new Map(products.map((p) => [p.slug, p]));
  const seen = new Set([...viewed, ...listed]);
  const weight = new Map<string, number>();
  const add = (slug: string, w: number) => {
    const p = bySlug.get(slug);
    if (p) weight.set(p.categorySlug, (weight.get(p.categorySlug) ?? 0) + w);
  };
  viewed.forEach((slug, i) => add(slug, viewed.length - i)); // most recent view weighs most
  listed.forEach((slug) => add(slug, 2));

  // A picture-led section: products with a picture first, ones without only if there aren't enough
  const unseen = products.filter((p) => !seen.has(p.slug));
  const candidates = [...unseen.filter((p) => p.image), ...unseen.filter((p) => !p.image)];
  // The visitor's categories take turns, strongest first (biscuits, marshmallow, biscuits, …), so one
  // strong interest doesn't push out the others
  const interests = [...weight.entries()].sort((a, b) => b[1] - a[1]).map(([slug]) => slug);
  const picked = mixAcrossCategories(
    interests.flatMap((slug) => candidates.filter((p) => p.categorySlug === slug)),
    count,
  );
  const taken = new Set(picked);
  const rest = candidates.filter((p) => !taken.has(p));
  const withPicture = mixAcrossCategories(rest.filter((p) => p.image), count - picked.length);
  const fill = [...withPicture, ...mixAcrossCategories(rest.filter((p) => !p.image), count - picked.length - withPicture.length)];
  let out = [...picked, ...fill];
  if (out.length < count) {
    // Visitor saw (almost) everything: top up with seen products, pictures first
    const inOut = new Set(out);
    const seenProducts = products.filter((p) => seen.has(p.slug) && !inOut.has(p));
    out = [...out, ...seenProducts.filter((p) => p.image), ...seenProducts.filter((p) => !p.image)].slice(0, count);
  }

  // Reason: which history produced the personal picks (by the categories they come from)
  const catsOf = (slugs: string[]) => new Set(slugs.map((s) => bySlug.get(s)?.categorySlug).filter(Boolean));
  const fromViewed = catsOf(viewed);
  const fromListed = catsOf(listed);
  const byViewed = picked.some((p) => fromViewed.has(p.categorySlug));
  const byListed = picked.some((p) => fromListed.has(p.categorySlug));
  const reason: Reason = byViewed && byListed ? 'both' : byViewed ? 'viewed' : byListed ? 'listed' : null;
  return { products: out, reason };
}
