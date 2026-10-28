'use client';
// Marketplace-style search: pick a category, type a name or item number, see matches instantly.
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';
import type { Category } from '@/lib/api';
import { matchesSearch, searchEntry } from '@/lib/catalogue';
import { useCatalogue } from './CatalogueContext';

export default function HomeSearch({ categories }: { categories: Category[] }) {
  const products = useCatalogue();
  const router = useRouter();
  const [q, setQ] = useState('');
  const [cat, setCat] = useState('');
  const [open, setOpen] = useState(false);

  const index = useMemo(() => products.map((p) => ({ p, entry: searchEntry(p) })), [products]);
  const matches = useMemo(
    () => index.filter(({ p, entry }) => (!cat || p.categorySlug === cat) && matchesSearch(entry, q)).map(({ p }) => p).slice(0, 6),
    [q, cat, index],
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (matches[0]) router.push(`/products/${matches[0].slug}`);
    else if (cat) router.push(`/categories/${cat}`);
  }

  return (
    <form onSubmit={submit} className="relative" role="search">
      <div className="flex overflow-hidden rounded-full border-2 border-gold bg-white shadow-sm focus-within:ring-4 focus-within:ring-gold/20">
        <select
          value={cat}
          onChange={(e) => setCat(e.target.value)}
          className="hidden border-r border-slate-200 bg-slate-50 px-4 text-sm text-slate-700 outline-none sm:block"
          aria-label="Category"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.slug} value={c.slug}>{c.name}</option>
          ))}
        </select>
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Search wafers, chocolate bars, biscuits or an item number like 801"
          className="min-w-0 flex-1 px-4 py-3 text-sm text-slate-900 outline-none"
          aria-label="Search products"
        />
        <button type="submit" className="m-1 flex items-center gap-2 rounded-full bg-ink px-5 text-sm font-semibold text-white hover:bg-ink-soft">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
          </svg>
          <span className="hidden sm:inline">Search</span>
        </button>
      </div>

      {open && q.trim() && (
        <div className="absolute inset-x-0 top-full z-30 mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
          {matches.length ? (
            matches.map((p) => (
              <Link key={p.slug} href={`/products/${p.slug}`} className="flex items-center gap-3 px-4 py-2 hover:bg-paper">
                {p.image ? (
                  <Image src={p.image} alt="" width={56} height={42} className="h-10 w-14 rounded object-cover" />
                ) : (
                  <span className="h-10 w-14 rounded bg-paper" />
                )}
                <span className="flex-1 text-sm font-medium text-slate-900">{p.name}</span>
                <span className="text-xs text-slate-500">{p.categoryName}</span>
              </Link>
            ))
          ) : (
            <p className="px-4 py-3 text-sm text-slate-600">
              No product matches “{q}”. <Link href="/contact" className="font-semibold text-gold-dark hover:underline">Ask our team</Link>: we also make to your recipe.
            </p>
          )}
        </div>
      )}
    </form>
  );
}
