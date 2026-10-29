'use client';
// The product range on the home page: category tabs, product cards, a quick-view window and an
// "enquiry list". Buyers collect several products and send one enquiry for all of them.
// The list is kept in this browser only (localStorage); nothing is sent until they submit the form.
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import EnquiryButton from '@/components/public/EnquiryButton';
import Reveal from '@/components/public/Reveal';
import type { Category } from '@/lib/api';
import type { CatalogueItem, HomeProduct } from '@/lib/catalogue';
import { readEnquiryList, rememberViewed, saveEnquiryList } from '@/lib/history';
import { useCatalogue } from './CatalogueContext';

const LIST_MAX = 20; // 20 lines of products leave room for the buyer's own message (4000 characters in all)
const PAGE = 12;

function itemNumbers(items: CatalogueItem[]): string {
  if (!items.length) return 'On request';
  const first = items.slice(0, 2).map((i) => i.no).join(', ');
  return items.length > 2 ? `${first} +${items.length - 2}` : first;
}

/** A product picture that fades in once it has loaded, instead of popping in.
 *  Visible by default (server HTML, no JavaScript); only a picture still loading after the page starts
 *  is hidden, until it loads or fails (a failed one shows the browser's fallback). */
function CardImage({ src, alt }: { src: string; alt: string }) {
  const img = useRef<HTMLImageElement>(null);
  const [pending, setPending] = useState(false);
  useEffect(() => {
    if (img.current && !img.current.complete) setPending(true);
  }, []);
  return (
    <Image
      ref={img}
      src={src}
      alt={alt}
      fill
      sizes="(max-width: 768px) 50vw, 25vw"
      onLoad={() => setPending(false)}
      onError={() => setPending(false)}
      className={`object-cover transition-[opacity,transform] duration-500 group-hover:scale-105 ${pending ? 'opacity-0' : 'opacity-100'}`}
    />
  );
}

export default function ProductExplorer({ categories }: { categories: Category[] }) {
  const products = useCatalogue();
  const [tab, setTab] = useState('all');
  const [shown, setShown] = useState(PAGE);
  const [quick, setQuick] = useState<HomeProduct | null>(null);
  const [list, setList] = useState<string[]>([]);
  const [sent, setSent] = useState(false);

  // Load the saved list, keeping only products that are still on the site (a hidden or deleted
  // product would otherwise use up a slot that nobody can see or remove)
  useEffect(() => {
    const live = new Set(products.map((p) => p.slug));
    const kept = readEnquiryList().filter((s) => live.has(s)).slice(0, LIST_MAX);
    setList(kept);
    saveEnquiryList(kept);
  }, [products]);

  useEffect(() => {
    if (!quick) return;
    // Not while the enquiry form opened from it is on top: that would throw away what was typed
    const close = (e: KeyboardEvent) => e.key === 'Escape' && !document.querySelector('[data-enquiry-modal]') && setQuick(null);
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [quick]);

  function saveList(next: string[]) {
    setList(next);
    saveEnquiryList(next);
  }

  function toggle(slug: string) {
    if (list.includes(slug)) saveList(list.filter((s) => s !== slug));
    else if (list.length < LIST_MAX) saveList([...list, slug]);
    else alert(`Your enquiry list can hold ${LIST_MAX} products. Send it first, then start a new one.`);
  }

  // After a successful send the saved list is emptied at once; the bar stays until the
  // "Thank you" window is closed, then disappears
  function onListSent() {
    saveEnquiryList([]);
    setSent(true);
  }
  function onListClosed() {
    if (!sent) return;
    setSent(false);
    setList([]);
  }

  const tabs = categories.filter((c) => products.some((p) => p.categorySlug === c.slug));
  const visible = useMemo(() => (tab === 'all' ? products : products.filter((p) => p.categorySlug === tab)), [tab, products]);
  const picked = products.filter((p) => list.includes(p.slug));
  const listMessage =
    'Enquiry list from the website:\n' +
    picked.map((p) => `- ${p.name} (items ${p.items.map((i) => i.no).join(', ') || 'n/a'})`).join('\n');

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
          const inList = list.includes(p.slug);
          return (
            // Cards pop in, row by row, every time they scroll into view (down or up)
            <Reveal key={p.slug} stagger repeat className="flex">
              <article className="card group flex w-full flex-col overflow-hidden transition-shadow hover:shadow-lg">
                <button onClick={() => { setQuick(p); rememberViewed(p.slug); }} className="relative block aspect-[4/3] overflow-hidden bg-paper" aria-label={`Quick view: ${p.name}`}>
                  {p.image ? (
                    <CardImage src={p.image} alt={p.name} />
                  ) : (
                    <span className="absolute inset-0 flex items-center justify-center text-xs text-slate-400">{p.categoryName}</span>
                  )}
                  {p.items.length > 1 && (
                    <span className="absolute left-2 top-2 rounded-full bg-white/90 px-2 py-0.5 text-[11px] font-semibold text-slate-700 shadow-sm">
                      {p.items.length} variants
                    </span>
                  )}
                  {p.privateLabel && (
                    <span className="absolute right-2 top-2 hidden rounded-full bg-gold px-2 py-0.5 text-[11px] font-bold text-ink shadow-sm sm:inline">Private label</span>
                  )}
                  <span className="absolute inset-x-0 bottom-0 translate-y-full bg-ink/85 py-1.5 text-center text-xs font-semibold text-white transition-transform group-hover:translate-y-0">
                    Quick view
                  </span>
                </button>
                <div className="flex flex-1 flex-col p-3 md:p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-gold-dark">{p.categoryName}</p>
                  <Link href={`/products/${p.slug}`} className="mt-1 line-clamp-1 font-semibold text-slate-900 hover:text-forest">{p.name}</Link>
                  <p className="mt-1 line-clamp-1 text-xs text-slate-500">{p.packFormats}</p>
                  <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                    <dt className="text-slate-500">Item no.</dt>
                    <dd className="truncate font-medium text-slate-800">{itemNumbers(p.items)}</dd>
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
            </Reveal>
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
              {quick.image && <Image src={quick.image} alt={quick.name} fill sizes="(max-width: 768px) 100vw, 50vw" className="object-contain" />}
            </div>
            <div className="flex flex-col p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="eyebrow">{quick.categoryName}</p>
                  <h3 className="mt-1 text-2xl font-bold">{quick.name}</h3>
                </div>
                <button onClick={() => setQuick(null)} className="text-slate-500 hover:text-slate-900" aria-label="Close">✕</button>
              </div>
              <p className="mt-3 text-sm text-slate-700">{quick.summary}</p>
              <div className="mt-4 max-h-60 overflow-y-auto rounded-lg border border-slate-200">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-paper text-slate-600">
                    <tr><th className="px-3 py-2">Item</th><th className="px-3 py-2">Variant</th><th className="px-3 py-2">Weight</th><th className="px-3 py-2">Pcs / box</th><th className="px-3 py-2">Per case</th></tr>
                  </thead>
                  <tbody>
                    {quick.items.map((i) => (
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

      {/* Enquiry list bar: on laptops it sits between the WhatsApp (left) and Koko (right) buttons;
          on smaller screens it sits above them so they don't overlap.
          Centred with inset-x-0 + mx-auto, not a transform (see EnquiryButton). */}
      {picked.length > 0 && (
        <div className="fixed inset-x-0 bottom-20 z-40 mx-auto flex w-[calc(100%-2rem)] max-w-xl items-center lg:bottom-5 lg:w-[calc(100%-9rem)] gap-3 rounded-full border border-slate-200 bg-white py-2 pl-3 pr-2 shadow-2xl">
          <div className="hidden -space-x-3 sm:flex">
            {picked.filter((p) => p.image).slice(0, 4).map((p) => (
              <Image key={p.slug} src={p.image!} alt="" width={40} height={30} className="h-8 w-10 rounded-md object-cover ring-2 ring-white" />
            ))}
          </div>
          <p className="min-w-0 flex-1 truncate text-sm">
            <span className="font-semibold">{picked.length}</span> in your enquiry list
          </p>
          <button onClick={() => saveList([])} className="text-xs text-slate-500 hover:text-slate-900">Clear</button>
          <EnquiryButton
            label="Send enquiry"
            source="quote"
            extraMessage={listMessage}
            title={`Enquiry for ${picked.length} product${picked.length > 1 ? 's' : ''}`}
            onSent={onListSent}
            onClose={onListClosed}
            className="btn-dark rounded-full !py-1.5 text-xs"
          />
        </div>
      )}
    </>
  );
}
