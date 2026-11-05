import type { MetadataRoute } from 'next';
import { serverGet, type Category, type Product } from '@/lib/api';

// Public URL of the site. Set SITE_URL in production (domain decision: backlog D7).
const BASE = process.env.SITE_URL || 'http://localhost:3000';

export const dynamic = 'force-dynamic';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [categories, products] = await Promise.all([
    serverGet<Category[]>('/public/categories').catch(() => null),
    serverGet<Product[]>('/public/products').catch(() => null),
  ]);
  const paths = [
    '/', '/products', '/private-label', '/partners', '/contact',
    ...(categories ?? []).map((c) => `/categories/${c.slug}`),
    ...(products ?? []).map((p) => `/products/${p.slug}`),
  ];
  return paths.map((p) => ({ url: `${BASE}${p}`, changeFrequency: 'weekly' }));
}
