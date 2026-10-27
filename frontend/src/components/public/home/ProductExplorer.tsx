'use client';
// The product range on the home page: category tabs, product cards, a quick-view window and an
// "enquiry list". Buyers collect several products and send one enquiry for all of them.
// The list is kept in this browser only (localStorage); nothing is sent until they submit the form.
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import EnquiryButton from '@/components/public/EnquiryButton';
import type { Category, Product } from '@/lib/api';
import { imageOf, parseItems, summary, type CatalogueItem } from '@/lib/catalogue';

const LIST_KEY = 'kjs_enquiry_list';
const LIST_MAX = 20; // keeps the enquiry message under the API's 4000-character limit
const PAGE = 12;

type Props = { products: Product[]; categories: Category[] };

function itemNumbers(items: CatalogueItem[]): string {
  if (!items.length) return 'On request';
  const first = items.slice(0, 2).map((i) => i.no).join(', ');
  return items.length > 2 ? `${first} +${items.length - 2}` : first;
}

export default function ProductExplorer({ products, categories }: Props) {
  const [tab, setTab] = useState('all');
  const [shown, setShown] = useState(PAGE);
  const [quick, setQuick] = useState<Product | null>(null);
  const [list, setList] = useState<string[]>([]);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(LIST_KEY) || '[]');
      if (Array.isArray(saved)) setList(saved.filter((s) => typeof s === 'string').slice(0, LIST_MAX));
    } catch {
      // private window or blocked storage: start with an empty list
    }
  }, []);

  useEffect(() => {
    if (!quick) return;
    const close = (e: KeyboardEvent) => e.key === 'Escape' && setQuick(null);
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [quick]);

  function saveList(next: string[]) {
    setList(next);
    try {
      localStorage.setItem(LIST_KEY, JSON.stringify(next));
    } catch {
      // the list still works for this visit
    }
  }
  function toggle(slug: string) {
    if (list.includes(slug)) saveList(list.filter((s) => s !== slug));
    else if (list.length < LIST_MAX) saveList([...list, slug]);
    else alert(`Your enquiry list can hold ${LIST_MAX} products. Send it first, then start a new one.`);
  }

  const tabs = categories.filter((c) => products.some((p) => p.category_slug === c.slug));
  const visible = useMemo(() => (tab === 'all' ? products : products.filter((p) => p.category_slug === tab)), [tab, products]);
  const picked = products.filter((p) => list.includes(p.slug));
  const listMessage =
    'Enquiry list from the website:\n' +
    picked.map((p) => `- ${p.name} (items ${parseItems(p.description).map((i) => i.no).join(', ') || 'n/a'})`).join('\n');

  return (
    <>
      <div className="flex flex-wrap gap-2" role="tablist">
        {[{ slug: 'all', name: 'All products', count: products.length }, ...tabs.map((c) => ({ slug: c.slug, name: c.name, count: c.product_count }))].map((t) => (
          <button
            key={t.slug}
            role="tab"
            aria-selected={tab === t.slug}
            onClick={() => { setTab(t.slug); setShown(PAGE); }}
            className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.slug ? 'bg-ink text-white' : 'border border-slate-200 bg-white text-slate-700 hover:border-gold'
            }`}
          >
            {t.name} <span className={tab === t.slug ? 'text-gold-light' : 'text-slate-400'}>{t.count}</span>
          </button>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3 md:gap-4 lg:grid-cols-4">
        {visible.slice(0, shown).map((p) => {
          const items = parseItems(p.description);
          const inList = list.includes(p.slug);
          return (
            <article key={p.slug} className="card group flex flex-col overflow-hidden transition-shadow hover:shadow-lg">
              <button onClick={() => setQuick(p)} className="relative block aspect-[4/3] overflow-hidden bg-paper" aria-label={`Quick view: ${p.name}`}>
                {imageOf(p) ? (
                  <Image src={imageOf(p)!} alt={p.name} fill sizes="(max-width: 768px) 50vw, 25vw" className="object-cover transition-transform duration-300 group-hover:scale-105" />
                ) : (
                  <span className="absolute inset-0 flex items-center justify-center text-xs text-slate-400">{p.category_name}</span>
                )}
                {items.length > 1 && (
                  <span className="absolute left-2 top-2 rounded-full bg-white/90 px-2 py-0.5 text-[11px] font-semibold text-slate-700 shadow-sm">
                    {items.length} variants
                  </span>
                )}
                {p.private_label && (
                  <span className="absolute right-2 top-2 hidden rounded-full bg-gold px-2 py-0.5 text-[11px] font-bold text-ink shadow-sm sm:inline">Private label</span>
                )}
                <span className="absolute inset-x-0 bottom-0 translate-y-full bg-ink/85 py-1.5 text-center text-xs font-semibold text-white transition-transform group-hover:translate-y-0">
                  Quick view
                </span>
              </button>
              <div className="flex flex-1 flex-col p-3 md:p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-gold-dark">{p.category_name}</p>
                <Link href={`/products/${p.slug}`} className="mt-1 line-clamp-1 font-semibold text-slate-900 hover:text-forest">{p.name}</Link>
                <p className="mt-1 line-clamp-1 text-xs text-slate-500">{p.pack_formats}</p>
                <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  <dt className="text-slate-500">Item no.</dt>
                  <dd className="truncate font-medium text-slate-800">{itemNumbers(items)}</dd>
                  <dt className="text-slate-500">Min. order</dt>
                  <dd className="truncate font-medium text-slate-800">{p.moq || 'On request'}</dd>
                </dl>
                <div className="mt-auto flex gap-2 pt-4">
                  <EnquiryButton label="Get quote" source="quote" productSlug={p.slug} title={`Quote for ${p.name}`} className="btn-gold flex-1 !px-2 !py-1.5 text-xs" />
                  <button
                    onClick={() => toggle(p.slug)}
                    aria-pressed={inList}
                    className={`btn !px-2 !py-1.5 text-xs ${inList ? 'border border-forest bg-forest/10 text-forest' : 'border border-slate-300 text-slate-700 hover:border-gold'}`}
                    title={inList ? 'Remove from enquiry list' : 'Add to enquiry list'}
                  >
                    {inList ? '✓ Listed' : '+ List'}
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {visible.length > shown && (
        <div className="mt-8 text-center">
          <button onClick={() => setShown((n) => n + PAGE)} className="btn-ghost">
            Show more ({visible.length - shown} left)
          </button>
        </div>
      )}

      {/* Quick view */}
      {quick && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label={quick.name}
          onClick={(e) => e.target === e.currentTarget && setQuick(null)}
        >
          <div className="grid max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white shadow-2xl md:grid-cols-2">
            <div className="relative aspect-[4/3] bg-paper md:aspect-auto">
              {imageOf(quick) && <Image src={imageOf(quick)!} alt={quick.name} fill sizes="(max-width: 768px) 100vw, 50vw" className="object-contain" />}
            </div>
            <div className="flex flex-col p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="eyebrow">{quick.category_name}</p>
                  <h3 className="mt-1 text-2xl font-bold">{quick.name}</h3>
                </div>
                <button onClick={() => setQuick(null)} className="text-slate-500 hover:text-slate-900" aria-label="Close">✕</button>
              </div>
              <p className="mt-3 text-sm text-slate-700">{summary(quick.description)}</p>
              <div className="mt-4 max-h-60 overflow-y-auto rounded-lg border border-slate-200">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-paper text-slate-600">
                    <tr><th className="px-3 py-2">Item</th><th className="px-3 py-2">Variant</th><th className="px-3 py-2">Weight</th><th className="px-3 py-2">Pcs / box</th><th className="px-3 py-2">Per case</th></tr>
                  </thead>
                  <tbody>
                    {parseItems(quick.description).map((i) => (
                      <tr key={i.no} className="border-t border-slate-100">
                        <td className="px-3 py-1.5 font-semibold">{i.no}</td>
                        <td className="px-3 py-1.5 text-slate-600">{i.variant || 'Standard'}</td>
                        <td className="px-3 py-1.5">{i.weight}</td>
                        <td className="px-3 py-1.5">{i.pieces}</td>
                        <td className="px-3 py-1.5">{i.perCase}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-slate-500">Prices and minimum order quantities on request. Available as private label in your pack design.</p>
              <div className="mt-auto flex flex-wrap gap-2 pt-5">
                <EnquiryButton label="Get quote" source="quote" productSlug={quick.slug} title={`Quote for ${quick.name}`} />
                <button onClick={() => toggle(quick.slug)} className="btn-ghost">
                  {list.includes(quick.slug) ? '✓ In enquiry list' : '+ Add to enquiry list'}
                </button>
                <Link href={`/products/${quick.slug}`} className="btn px-2 text-slate-700 hover:text-ink">Full details →</Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Enquiry list bar: sits between the WhatsApp (left) and Koko (right) buttons */}
      {picked.length > 0 && (
        <div className="fixed bottom-5 left-1/2 z-40 flex w-[calc(100%-9rem)] max-w-xl -translate-x-1/2 items-center gap-3 rounded-full border border-slate-200 bg-white py-2 pl-3 pr-2 shadow-2xl">
          <div className="hidden -space-x-3 sm:flex">
            {picked.filter(imageOf).slice(0, 4).map((p) => (
              <Image key={p.slug} src={imageOf(p)!} alt="" width={40} height={30} className="h-8 w-10 rounded-md object-cover ring-2 ring-white" />
            ))}
          </div>
          <p className="min-w-0 flex-1 truncate text-sm">
            <span className="font-semibold">{picked.length}</span> in your enquiry list
          </p>
          <button onClick={() => saveList([])} className="hidden text-xs text-slate-500 hover:text-slate-900 sm:block">Clear</button>
          <EnquiryButton
            label="Send enquiry"
            source="quote"
            extraMessage={listMessage}
            title={`Enquiry for ${picked.length} product${picked.length > 1 ? 's' : ''}`}
            className="btn-dark rounded-full !py-1.5 text-xs"
          />
        </div>
      )}
    </>
  );
}
