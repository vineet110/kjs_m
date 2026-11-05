'use client';
// Left-hand category menu. Hovering (or tabbing to) a category opens a panel with its products
// (desktop); on phones it becomes a row of chips.
// Confectionery is a dropdown: Chocolate bars, Wafers, Biscuits, Marshmallow & cakes sit inside it
// (SUBCATEGORIES in lib/catalogue.ts). It opens on hover, or with its arrow button (touch, keyboard).
import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import type { Category } from '@/lib/api';
import { SUBCATEGORIES } from '@/lib/catalogue';
import { useCatalogue } from './CatalogueContext';

const CHILDREN = new Set(Object.values(SUBCATEGORIES).flat());

export default function CategoryMenu({ categories }: { categories: Category[] }) {
  const products = useCatalogue();
  const [hover, setHover] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null); // the dropdown that is open
  const active = categories.find((c) => c.slug === hover);
  // A parent's panel shows the products of all its subcategories
  const activeSlugs = active ? [active.slug, ...(SUBCATEGORIES[active.slug] ?? [])] : [];
  const inActive = products.filter((p) => activeSlugs.includes(p.categorySlug));
  const top = categories.filter((c) => !CHILDREN.has(c.slug));
  const childrenOf = (slug: string) => (SUBCATEGORIES[slug] ?? []).map((s) => categories.find((c) => c.slug === s)).filter((c): c is Category => !!c);

  const row = (c: Category, sub = false) => {
    const count = c.product_count; // a parent's count already includes its subcategories (API)
    return (
      <Link
        href={`/categories/${c.slug}`}
        onMouseEnter={() => setHover(c.slug)}
        onFocus={() => setHover(c.slug)}
        className={`flex flex-1 items-center justify-between py-2 text-sm ${sub ? 'pl-8 pr-4' : 'px-4'} ${hover === c.slug ? 'bg-paper font-semibold text-ink' : 'text-slate-700'}`}
      >
        <span>{c.name}</span>
        {count > 0 && <span className="text-xs text-slate-400">{count}</span>}
      </Link>
    );
  };

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
        onMouseLeave={() => { setHover(null); setOpen(null); }}
        // Close when keyboard focus moves outside the menu and its panel, or on Escape.
        // (Clicking empty space gives no relatedTarget: the mouse handlers decide then.)
        onBlur={(e) => e.relatedTarget && !e.currentTarget.contains(e.relatedTarget) && (setHover(null), setOpen(null))}
        onKeyDown={(e) => e.key === 'Escape' && (setHover(null), setOpen(null))}
        aria-label="Product categories"
      >
        <div className="card flex h-full flex-col py-2">
          <p className="px-4 pb-2 pt-1 text-xs font-bold uppercase tracking-widest text-slate-500">Categories</p>
          <ul>
            {top.map((c) => {
              const subs = childrenOf(c.slug);
              if (!subs.length) return <li key={c.slug} className="flex">{row(c)}</li>;
              const isOpen = open === c.slug;
              return (
                <li key={c.slug} onMouseEnter={() => setOpen(c.slug)}>
                  <div className="flex">
                    {row(c)}
                    <button
                      type="button"
                      onClick={() => setOpen(isOpen ? null : c.slug)}
                      aria-expanded={isOpen}
                      aria-controls={`sub-${c.slug}`}
                      aria-label={`${isOpen ? 'Hide' : 'Show'} ${c.name} types`}
                      className={`px-3 text-slate-500 hover:text-ink ${hover === c.slug ? 'bg-paper' : ''}`}
                    >
                      <span className={`inline-block text-xs transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}>▾</span>
                    </button>
                  </div>
                  <ul id={`sub-${c.slug}`} hidden={!isOpen} className="border-l-2 border-gold/60 ml-4">
                    {subs.map((s) => <li key={s.slug} className="flex">{row(s, true)}</li>)}
                  </ul>
                </li>
              );
            })}
          </ul>
          {/* Fills the space under a short list: a picture of our chocolate bars, linking to them */}
          <Link href="/categories/confectionery" className="group relative mx-3 mb-1 mt-auto block overflow-hidden rounded-lg pt-3">
            <Image src="/images/categories/confectionery.jpg" alt="KJS India chocolate bars" width={400} height={250} className="aspect-[4/3] w-full rounded-lg object-cover transition-transform duration-500 group-hover:scale-105" />
            <span className="absolute inset-x-0 bottom-0 rounded-b-lg bg-gradient-to-t from-ink/85 to-transparent px-3 pb-2.5 pt-8 text-sm font-semibold text-white">
              Chocolate bars & wafers <span aria-hidden="true" className="inline-block transition-transform group-hover:translate-x-1">→</span>
            </span>
          </Link>
        </div>

        {active && (
          // The 8px space between the list and the panel is padding of this wrapper (not a margin),
          // so it belongs to the menu: crossing it with the mouse doesn't fire onMouseLeave
          <div className="absolute left-full top-0 z-30 h-full pl-2">
            <div className="h-full w-[640px] overflow-y-auto rounded-xl border border-slate-200 bg-white p-5 shadow-2xl">
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
          </div>
        )}
      </nav>
    </>
  );
}
