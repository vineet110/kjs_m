// What a visitor did on the site, kept in THIS browser only (localStorage), never sent to us:
// products they opened, and their enquiry list. Used for "Recommended for you" on the home page.
// Every read and write is wrapped: storage can be blocked (private window) and the site must still work.
import type { HomeProduct } from './catalogue';

const LIST_KEY = 'kjs_enquiry_list'; // the enquiry list (ProductExplorer)
const VIEWED_KEY = 'kjs_viewed';
const VIEWED_MAX = 12;
/** Fired on window when the history or the enquiry list changes (RecommendedProducts listens). */
export const HISTORY_EVENT = 'kjs:history';

function write(key: string, list: string[]) {
  try {
    localStorage.setItem(key, JSON.stringify(list));
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
  for (const p of products) byCat.set(p.categorySlug, [...(byCat.get(p.categorySlug) ?? []), p]);
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
 * across categories. With no history it is just that mix.
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
  const ranked = candidates
    .map((p, i) => ({ p, w: weight.get(p.categorySlug) ?? 0, i }))
    .filter((x) => x.w > 0)
    .sort((a, b) => b.w - a.w || a.i - b.i)
    .map((x) => x.p);
  const picked = ranked.slice(0, count);
  const rest = candidates.filter((p) => !picked.includes(p));
  const withPicture = mixAcrossCategories(rest.filter((p) => p.image), count - picked.length);
  const fill = [...withPicture, ...mixAcrossCategories(rest.filter((p) => !p.image), count - picked.length - withPicture.length)];
  const known = (slugs: string[]) => slugs.some((slug) => products.some((p) => p.slug === slug));
  const reason: Reason = !picked.length ? null : known(viewed) && known(listed) ? 'both' : known(viewed) ? 'viewed' : 'listed';
  return { products: [...picked, ...fill], reason };
}
