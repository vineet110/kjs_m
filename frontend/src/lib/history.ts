// What a visitor did on the site, kept in THIS browser only (localStorage), never sent to us:
// products they opened, and their enquiry list. Used for "Recommended for you" on the home page.
// Every read and write is wrapped: storage can be blocked (private window) and the site must still work.
import type { HomeProduct } from './catalogue';

const LIST_KEY = 'kjs_enquiry_list'; // the enquiry list (ProductExplorer)
const VIEWED_KEY = 'kjs_viewed';
const VIEWED_MAX = 12;
/** Fired on window when the history or the enquiry list changes (RecommendedProducts listens). */
export const HISTORY_EVENT = 'kjs:history';

// Saves, and tells listeners, only when something really changed (no needless work on every load)
function write(key: string, list: string[]) {
  const next = JSON.stringify(list);
  try {
    if (localStorage.getItem(key) === next) return;
    localStorage.setItem(key, next);
  } catch {
    // storage blocked: works for this visit only
  }
  window.dispatchEvent(new Event(HISTORY_EVENT));
}

function read(key: string): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(v) ? v.filter((s): s is string => typeof s === 'string') : [];
  } catch {
    return [];
  }
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
  const seen = new Set([...viewed, ...listed]);
  const weight = new Map<string, number>();
  const add = (slug: string, w: number) => {
    const p = products.find((x) => x.slug === slug);
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
  const ranked = mixAcrossCategories(
    interests.flatMap((slug) => candidates.filter((p) => p.categorySlug === slug)),
    count,
  );
  const picked = ranked.slice(0, count);
  const rest = candidates.filter((p) => !picked.includes(p));
  const withPicture = mixAcrossCategories(rest.filter((p) => p.image), count - picked.length);
  const fill = [...withPicture, ...mixAcrossCategories(rest.filter((p) => !p.image), count - picked.length - withPicture.length)];
  let out = [...picked, ...fill];
  if (out.length < count) {
    // Visitor saw (almost) everything: top up with seen products, pictures first
    const seenProducts = products.filter((p) => seen.has(p.slug) && !out.includes(p));
    out = [...out, ...seenProducts.filter((p) => p.image), ...seenProducts.filter((p) => !p.image)].slice(0, count);
  }

  // Reason: which history produced the personal picks (by the categories they come from)
  const catsOf = (slugs: string[]) => new Set(products.filter((p) => slugs.includes(p.slug)).map((p) => p.categorySlug));
  const fromViewed = catsOf(viewed);
  const fromListed = catsOf(listed);
  const byViewed = picked.some((p) => fromViewed.has(p.categorySlug));
  const byListed = picked.some((p) => fromListed.has(p.categorySlug));
  const reason: Reason = byViewed && byListed ? 'both' : byViewed ? 'viewed' : byListed ? 'listed' : null;
  return { products: out, reason };
}
