'use client';
// Marketplace-style search: pick a category, type a name or item number, see matches instantly.
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import type { Category } from '@/lib/api';
import { isUploaded, matchesSearch, searchEntry } from '@/lib/catalogue';
import { cancelSearch, trackSearch } from '@/lib/insights';
import { startNavigationProgress } from '../NavigationProgress';
import { useCatalogue } from './CatalogueContext';

/** typing: example searches (real product names) type themselves in the empty box (site_ui.ini typing_search) */
export default function HomeSearch({ categories, coffee = false, typing = false }: { categories: Category[]; coffee?: boolean; typing?: boolean }) {
  const products = useCatalogue();
  const router = useRouter();
  const [q, setQ] = useState('');
  const [cat, setCat] = useState('');
  const [open, setOpen] = useState(false);
  const fixedHint = coffee ? 'Search instant coffee, 3-in-1 premix...' : 'Search wafers, chocolate bars, biscuits, coffee...';
  const [hint, setHint] = useState(fixedHint);
  const [focused, setFocused] = useState(false);

  // Example searches typing themselves: only while the box is empty and not in use. Off for "reduce motion".
  useEffect(() => {
    if (!typing || focused || q || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setHint(fixedHint); return; }
    const examples = [fixedHint, ...products.slice(0, 4).map((p) => p.name)];
    let i = 0, j = 0, deleting = false;
    let t: ReturnType<typeof setTimeout>;
    const tick = () => {
      const word = examples[i];
      setHint(word.slice(0, j) + (j < word.length || deleting ? '|' : ''));
      if (!deleting && j < word.length) { j++; t = setTimeout(tick, 65); return; }
      if (!deleting) { deleting = true; t = setTimeout(tick, 1600); return; }
      if (j > 0) { j = Math.max(0, j - 2); t = setTimeout(tick, 25); return; }
      deleting = false; i = (i + 1) % examples.length; t = setTimeout(tick, 300);
    };
    t = setTimeout(tick, 1200);
    return () => clearTimeout(t);
  }, [typing, focused, q, products, fixedHint]);

  const index = useMemo(() => products.map((p) => ({ p, entry: searchEntry(p) })), [products]);
  const found = useMemo(
    () => index.filter(({ p, entry }) => (!cat || p.categorySlug === cat) && matchesSearch(entry, q)).map(({ p }) => p),
    [q, cat, index],
  );
  const matches = found.slice(0, 6);
  // Website insights: what was searched and how many products it found (recorded after a typing pause)
  useEffect(() => {
    if (q.trim()) trackSearch(q, found.length);
    else cancelSearch(); // cleared before the pause ended: nothing is recorded
  }, [q, found.length]);
  useEffect(() => cancelSearch, []); // the search box closed (another page): forget a waiting search

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const to = matches[0] ? `/products/${matches[0].slug}` : cat ? `/categories/${cat}` : null;
    if (!to) return;
    startNavigationProgress(); // router.push is not a link click, so the bar is started here
    router.push(to);
  }

  return (
    <form
      onSubmit={submit}
      className="relative"
      role="search"
      // Results stay open while focus is anywhere in the search box (input, button, result links):
      // keyboard users can Tab to the results. They close when focus leaves it, or on Escape.
      onBlur={(e) => !e.currentTarget.contains(e.relatedTarget) && setOpen(false)}
      onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
    >
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
          onFocus={() => { setOpen(true); setFocused(true); }}
          onBlur={() => setFocused(false)}
          onClick={() => setOpen(true)} // reopens after Escape (focus never left, so no new focus event)
          placeholder={hint}
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
        <div
          className="absolute inset-x-0 top-full z-30 mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl"
          // A mouse press here doesn't move focus, so the input keeps it and the list stays open until
          // the click lands (some browsers, e.g. Safari, don't focus links on click)
          onMouseDown={(e) => e.preventDefault()}
        >
          {matches.length ? (
            matches.map((p) => (
              <Link key={p.slug} href={`/products/${p.slug}`} className="flex items-center gap-3 px-4 py-2 hover:bg-paper">
                {p.image ? (
                  <Image src={p.image} unoptimized={isUploaded(p.image)} alt="" width={56} height={42} className="h-10 w-14 rounded object-cover" />
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
