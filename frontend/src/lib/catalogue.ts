// Catalogue products keep their item list inside the description, one line per item:
// "• Item 801 (variant): 25 g, 24 pieces per box, 6 per case" (written by backend/app/seed_catalogue.py).
// These helpers read it back so cards can show variants and item numbers.
import type { Product } from './api';

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

/** The first paragraph of the description, without the item list. */
export function summary(description: string): string {
  return description.split('\n\n')[0];
}

/** A picture from our own site folder, or null (empty, or an outside address Next.js would refuse). */
export function imageOf(p: Pick<Product, 'image_path'>): string | null {
  return p.image_path.startsWith('/') && !p.image_path.startsWith('//') ? p.image_path : null;
}

/** What the home page needs per product: small, with the item list already read.
 *  Sent to the browser once (see components/public/home/CatalogueContext.tsx). */
export type HomeProduct = {
  slug: string; name: string; categorySlug: string; categoryName: string; image: string | null;
  summary: string; packFormats: string; moq: string; privateLabel: boolean; items: CatalogueItem[];
};

export function toHomeProduct(p: Product): HomeProduct {
  return {
    slug: p.slug, name: p.name, categorySlug: p.category_slug, categoryName: p.category_name, image: imageOf(p),
    summary: summary(p.description), packFormats: p.pack_formats, moq: p.moq, privateLabel: p.private_label,
    items: parseItems(p.description),
  };
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
