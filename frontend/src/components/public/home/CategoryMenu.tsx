'use client';
// Left-hand category menu. Hovering (or tabbing to) a category opens a panel with its products
// (desktop); on phones it becomes a row of chips.
import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import type { Category } from '@/lib/api';
import { useCatalogue } from './CatalogueContext';

export default function CategoryMenu({ categories }: { categories: Category[] }) {
  const products = useCatalogue();
  const [hover, setHover] = useState<string | null>(null);
  const active = categories.find((c) => c.slug === hover);
  const inActive = active ? products.filter((p) => p.categorySlug === active.slug) : [];

  return (
    <>
      <div className="flex gap-2 overflow-x-auto pb-1 lg:hidden">
        {categories.map((c) => (
          <Link key={c.slug} href={`/categories/${c.slug}`} className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700">
            {c.name}
          </Link>
        ))}
      </div>

      <nav
        className="relative hidden h-full lg:block"
        onMouseLeave={() => setHover(null)}
        // Close when keyboard focus moves outside the menu and its panel, or on Escape.
        // (Clicking empty space gives no relatedTarget: the mouse handlers decide then.)
        onBlur={(e) => e.relatedTarget && !e.currentTarget.contains(e.relatedTarget) && setHover(null)}
        onKeyDown={(e) => e.key === 'Escape' && setHover(null)}
        aria-label="Product categories"
      >
        <div className="card h-full py-2">
          <p className="px-4 pb-2 pt-1 text-xs font-bold uppercase tracking-widest text-slate-500">Categories</p>
          <ul>
            {categories.map((c) => (
              <li key={c.slug}>
                <Link
                  href={`/categories/${c.slug}`}
                  onMouseEnter={() => setHover(c.slug)}
                  onFocus={() => setHover(c.slug)}
                  className={`flex items-center justify-between px-4 py-2 text-sm ${hover === c.slug ? 'bg-paper font-semibold text-ink' : 'text-slate-700'}`}
                >
                  <span>{c.name}</span>
                  <span className="text-xs text-slate-400">{c.product_count || 'On request'}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>

        {active && (
          <div className="absolute left-full top-0 z-30 ml-2 h-full w-[640px] overflow-y-auto rounded-xl border border-slate-200 bg-white p-5 shadow-2xl">
            <div className="flex items-baseline justify-between">
              <h3 className="text-lg font-bold">{active.name}</h3>
              <Link href={`/categories/${active.slug}`} className="text-sm font-semibold text-gold-dark hover:underline">View all →</Link>
            </div>
            <p className="mt-1 text-sm text-slate-600">{active.description}</p>
            {inActive.length ? (
              <div className="mt-4 grid grid-cols-4 gap-3">
                {inActive.slice(0, 12).map((p) => (
                  <Link key={p.slug} href={`/products/${p.slug}`} className="group text-center">
                    {p.image ? (
                      <Image src={p.image} alt={p.name} width={140} height={105} className="aspect-[4/3] w-full rounded-lg object-cover transition-transform group-hover:scale-105" />
                    ) : (
                      <span className="block aspect-[4/3] w-full rounded-lg bg-paper" />
                    )}
                    <span className="mt-1 block text-xs font-medium text-slate-700 group-hover:text-ink">{p.name}</span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="mt-6 rounded-lg bg-paper p-4 text-sm text-slate-600">
                Made to order for your brand. Ask us for formats, recipes and the catalogue.
              </p>
            )}
          </div>
        )}
      </nav>
    </>
  );
}
