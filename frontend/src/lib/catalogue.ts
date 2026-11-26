// Catalogue items. Since R19 a product has its own `items` list. Older API answers kept them inside the
// description, one line per item: "• Item 801 (variant): 25 g, 24 pieces per box, 6 per case"; parseItems
// still reads those, so a page never loses its items during a deploy.
import type { Category, Product, ProductItem } from './api';
import { asset } from './assets';

export type CatalogueItem = { no: string; variant: string; weight: string; pieces: string; perCase: string };

const ITEM = /^• Item (\S+)(?: \((.+)\))?: (.+?), (\d+) pieces per box, (\d+) per case$/;

export function parseItems(description: string): CatalogueItem[] {
  const items: CatalogueItem[] = [];
  for (const line of description.split('\n')) {
    const m = ITEM.exec(line.trim());
    if (m) items.push({ no: m[1], variant: m[2] ?? '', weight: m[3], pieces: m[4], perCase: m[5] });
  }
  return items;
}

/** A product's items: its own list, or (an older API answer) the lines in its description. */
export function itemsOf(p: Pick<Product, 'description'> & { items?: ProductItem[] }): CatalogueItem[] {
  if (p.items?.length)
    return p.items.map((i) => ({ no: i.no, variant: i.variant, weight: i.weight, pieces: String(i.pieces), perCase: String(i.per_case) }));
  return parseItems(p.description);
}

/** Admin > Products "Items" box: one item per line, "801 | Hazelnut | 25 g | 24 | 6" (variant may be empty). */
export function itemsToLines(items: ProductItem[] | undefined): string {
  return (items ?? []).map((i) => [i.no, i.variant, i.weight, i.pieces, i.per_case].join(' | ')).join('\n');
}

/** The "Items" box read back. A line that doesn't fit is reported with its number, never dropped (R19). */
export function itemsFromLines(text: string): { items: ProductItem[] } | { error: string } {
  const items: ProductItem[] = [];
  const lines = text.split('\n');
  for (let n = 0; n < lines.length; n++) {
    const line = lines[n].trim();
    if (!line) continue;
    const parts = line.split('|').map((x) => x.trim());
    const [no, variant, weight, pieces, perCase] = parts;
    const whole = (v: string | undefined) => (v && /^\d+$/.test(v) && Number(v) >= 1 ? Number(v) : null);
    if (parts.length !== 5 || !no || /\s/.test(no) || !weight || whole(pieces) === null || whole(perCase) === null)
      return { error: `Items, line ${n + 1}: write it as "item no | variant | weight | pieces per box | per case", e.g. "801 | Hazelnut | 25 g | 24 | 6" (variant may be empty).` };
    items.push({ no, variant: variant ?? '', weight, pieces: whole(pieces)!, per_case: whole(perCase)! });
  }
  return { items };
}

/** The first paragraph of the description, without the item list. */
export function summary(description: string): string {
  return description.split('\n\n')[0];
}

/** Categories shown inside another one (a dropdown in the home page menu). The database keeps them as
 *  separate categories; the API counts and lists them under the parent too (same list in
 *  backend/app/services/catalog_service.py). */

export const SUBCATEGORIES: Record<string, string[]> = {
  confectionery: ['chocolate-bars', 'wafers', 'biscuits', 'marshmallow-cakes'],
};

const CHILD_SLUGS = new Set(Object.values(SUBCATEGORIES).flat());
const topLevel = (cats: Category[] | null | undefined): Category[] => (cats ?? []).filter((c) => !CHILD_SLUGS.has(c.slug));

/** The site follows the category switches (Admin > Products): coffee-only when Coffee is the only top-level
 *  category the public sees. No list (API down) = the full site. */
export function coffeeOnly(cats: Category[] | null | undefined): boolean {
  const top = topLevel(cats);
  return top.length === 1 && top[0].slug === 'coffee';
}

/** A text from Admin > Website: its coffee version ("coffee." + key) when coffee-only and one is set. */
export function focusText(t: Record<string, string>, key: string, coffee: boolean): string | undefined {
  return (coffee ? t[`coffee.${key}`] : undefined) ?? t[key];
}

/** The range in words for the footer and Google: "coffee, health drinks and confectionery". */
export function rangeText(cats: Category[] | null | undefined): string {
  const names = topLevel(cats).map((c) => c.name.toLowerCase());
  if (names.length === 0) return 'coffee, tea, health drinks and confectionery';
  return names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

/** A picture from our own site folder (served from R2 when set, see lib/assets.ts), else the first photo
 *  uploaded in Admin > Products, else null (empty, or an outside address Next.js would refuse). */
export function imageOf(p: Pick<Product, 'image_path'> & Partial<Pick<Product, 'photo_url'>>): string | null {
  if (p.image_path.startsWith('/') && !p.image_path.startsWith('//')) return asset(p.image_path);
  return p.photo_url?.startsWith('/api/') ? p.photo_url : null;
}

/** An uploaded photo (served by our API, maybe a redirect to storage): the browser loads it as it is,
 *  like the product page does, instead of through Next.js's picture resizing. */
export const isUploaded = (src: string): boolean => src.startsWith('/api/');

/** What the home page needs per product: small, with the item list already read.
 *  Sent to the browser once (see components/public/home/CatalogueContext.tsx). */
export type HomeProduct = {
  slug: string; name: string; categorySlug: string; categoryName: string; image: string | null;
  summary: string; packFormats: string; moq: string; privateLabel: boolean; items: CatalogueItem[];
  offerPercent: number | null;
};

export function toHomeProduct(p: Product): HomeProduct {
  return {
    slug: p.slug, name: p.name, categorySlug: p.category_slug, categoryName: p.category_name, image: imageOf(p),
    summary: summary(p.description), packFormats: p.pack_formats, moq: p.moq, privateLabel: p.private_label,
    items: itemsOf(p), offerPercent: p.offer_percent ?? null,
  };
}

/** The offer badge text, or null when there is no offer (staff set it in Admin > Products). */
export function offerLabel(percent: number | null | undefined): string | null {
  return percent ? `Up to ${percent}% OFF` : null;
}

const SPLIT = /[\s,.;:!?()&/'"+–-]+/;

/** Lowercase without accents, so "kremali" finds "Kremalı" and "nestle" finds "Nestlé". */
function plain(text: string): string {
  return text.toLowerCase().replace(/ı/g, 'i').normalize('NFD').replace(/[̀-ͯ]/g, '');
}

export type SearchEntry = { tokens: string[]; numbers: string[] };

/** What search looks at, prepared once per product (not on every keystroke). */
export function searchEntry(p: HomeProduct): SearchEntry {
  return {
    tokens: plain([p.name, p.categoryName, p.summary, ...p.items.map((i) => i.variant)].join(' ')).split(SPLIT),
    numbers: p.items.map((i) => plain(i.no)),
  };
}

/** Search. Every typed word must match: an item number ("801", "600A"), or the start of a word in the
 *  name, category, summary or variants. Pack numbers like "24 pieces per box" are not searched,
 *  so typing "24" doesn't match every product. */
export function matchesSearch({ tokens, numbers }: SearchEntry, query: string): boolean {
  const words = plain(query).split(SPLIT).filter(Boolean);
  if (!words.length) return false;
  return words.every(
    (w) => tokens.some((t) => t.startsWith(w)) || numbers.some((n) => n === w || (w.length >= 3 && n.startsWith(w))),
  );
}
