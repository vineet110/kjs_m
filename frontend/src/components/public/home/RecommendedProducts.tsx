'use client';
// "Recommended for you" on the home page, from what this visitor opened or put in their enquiry list
// (kept in their browser only, see lib/history.ts). First-time visitors see "Recommended picks", a mix
// across categories. The picks need the browser's history, so the server (and the first paint) shows
// same-size placeholders instead of a mix that would then flash and change. Updates live when the
// visitor quick-views a product or changes their enquiry list on the same page.
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import Reveal from '@/components/public/Reveal';
import { HISTORY_EVENT, readEnquiryList, readViewed, recommend, type Reason } from '@/lib/history';
import { useCatalogue } from './CatalogueContext';

const COUNT = 8;
const EYEBROW: Record<Exclude<Reason, null>, string> = {
  viewed: 'Based on what you viewed',
  listed: 'Based on your enquiry list',
  both: 'Based on your browsing',
};

export default function RecommendedProducts() {
  const products = useCatalogue();
  const [picks, setPicks] = useState<ReturnType<typeof recommend> | null>(null);

  useEffect(() => {
    const update = () => setPicks(recommend(products, readViewed(), readEnquiryList(), COUNT));
    update();
    window.addEventListener(HISTORY_EVENT, update);
    return () => window.removeEventListener(HISTORY_EVENT, update);
  }, [products]);

  if (picks && !picks.products.length) return null;
  return (
    <section className="mx-auto max-w-7xl px-4 pt-14" aria-labelledby="recommended-title" aria-busy={!picks}>
      <p className="eyebrow">{picks?.reason ? EYEBROW[picks.reason] : 'Recommended'}</p>
      <h2 id="recommended-title" className="mt-2 text-3xl font-bold">
        {picks?.reason ? 'Recommended for you' : 'Recommended picks'}
      </h2>
      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
        {picks
          ? picks.products.map((p) => (
              <Reveal key={p.slug} stagger repeat className="flex">
                <Link href={`/products/${p.slug}`} className="card group flex w-full flex-col overflow-hidden transition-shadow hover:shadow-lg">
                  <div className="relative aspect-[4/3] overflow-hidden bg-paper">
                    {p.image ? (
                      <Image src={p.image} alt={p.name} fill sizes="(max-width: 768px) 50vw, 25vw" className="object-cover transition-transform duration-300 group-hover:scale-105" />
                    ) : (
                      <span className="absolute inset-0 flex items-center justify-center text-xs text-slate-400">{p.categoryName}</span>
                    )}
                  </div>
                  <div className="p-3 md:p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-gold-dark">{p.categoryName}</p>
                    <p className="mt-1 line-clamp-1 font-semibold text-slate-900 group-hover:text-forest">{p.name}</p>
                    <p className="mt-1 line-clamp-1 text-xs text-slate-500">{p.packFormats}</p>
                  </div>
                </Link>
              </Reveal>
            ))
          : Array.from({ length: COUNT }, (_, i) => (
              // Placeholders with the same size as a card, so nothing below jumps when the picks arrive
              <div key={i} className="card overflow-hidden" aria-hidden="true">
                <div className="aspect-[4/3] animate-pulse bg-slate-200/70 motion-reduce:animate-none" />
                <div className="space-y-2 p-3 md:p-4">
                  <div className="h-3 w-16 animate-pulse rounded bg-slate-200/70 motion-reduce:animate-none" />
                  <div className="h-4 w-28 animate-pulse rounded bg-slate-200/70 motion-reduce:animate-none" />
                  <div className="h-3 w-20 animate-pulse rounded bg-slate-200/70 motion-reduce:animate-none" />
                </div>
              </div>
            ))}
      </div>
    </section>
  );
}
