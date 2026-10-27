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

/** Lowercase text to search in: name, category, description (so item numbers like "801" match). */
export function searchText(p: Pick<Product, 'name' | 'category_name' | 'description'>): string {
  return `${p.name} ${p.category_name} ${p.description}`.toLowerCase();
}
