'use client';
// "Recommended" on the home page.
// - The server renders real products (a mix across categories, what a first-time visitor sees), so
//   Google and no-JS visitors get product names and links (public pages stay server-rendered).
// - After loading, a returning visitor gets personal picks from what they opened or put in their
//   enquiry list (kept in their browser only, see lib/history.ts): swapped in at once if the section is
//   off screen, with a short fade if it is already in view.
// - Later changes (a quick view, the enquiry list, another tab, back/forward) are applied only while
//   the section is off screen, so nothing reshuffles under the visitor's eyes.
// - Always the same number of cards (recommend() tops up), so nothing below ever jumps.
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import Reveal from '@/components/public/Reveal';
import { HISTORY_EVENT, readEnquiryList, readViewed, recommend, type Reason } from '@/lib/history';
import CardImage from './CardImage';
import { useCatalogue } from './CatalogueContext';

const COUNT = 8;
const FADE_MS = 200;
const EYEBROW: Record<Exclude<Reason, null>, string> = {
  viewed: 'Based on what you viewed',
  listed: 'Based on your enquiry list',
  both: 'Based on your browsing',
};
type Picks = ReturnType<typeof recommend>;
const same = (a: Picks, b: Picks) => a.reason === b.reason && a.products.map((p) => p.slug).join() === b.products.map((p) => p.slug).join();

export default function RecommendedProducts() {
  const products = useCatalogue();
  const section = useRef<HTMLElement>(null);
  const [picks, setPicks] = useState<Picks>(() => recommend(products, [], [], COUNT));
  const [fading, setFading] = useState(false);

  useEffect(() => {
    const el = section.current;
    if (!el) return;
    let onScreen = false;
    let pending: Picks | null = null;
    let timer = 0;
    const apply = (next: Picks, fade: boolean) => {
      if (!fade) return setPicks(next);
      setFading(true);
      timer = window.setTimeout(() => { setPicks(next); setFading(false); }, FADE_MS);
    };
    const latest = () => recommend(products, readViewed(), readEnquiryList(), COUNT);

    // Section visibility: a change that waited while it was on screen is applied once it leaves
    const io = new IntersectionObserver(([e]) => {
      onScreen = e.isIntersecting;
      if (!onScreen && pending) { setPicks(pending); pending = null; }
    });
    io.observe(el);

    // First load: personal picks at once (fade only if the section is already on screen)
    const first = latest();
    const r = el.getBoundingClientRect();
    if (!same(first, picks)) apply(first, r.top < window.innerHeight && r.bottom > 0);

    // Later changes: here (quick view, enquiry list), in other tabs ('storage'), or back/forward ('pageshow')
    const update = () => {
      const next = latest();
      if (onScreen) pending = next;
      else { pending = null; setPicks(next); }
    };
    window.addEventListener(HISTORY_EVENT, update);
    window.addEventListener('storage', update);
    window.addEventListener('pageshow', update);
    return () => {
      io.disconnect();
      window.clearTimeout(timer);
      window.removeEventListener(HISTORY_EVENT, update);
      window.removeEventListener('storage', update);
      window.removeEventListener('pageshow', update);
    };
    // `picks` is read once, for the first comparison only: re-running on every pick change isn't wanted
  }, [products]);

  if (!picks.products.length) return null; // no products at all: same on the server and in the browser
  return (
    <section ref={section} className="mx-auto max-w-7xl px-4 pt-14" aria-labelledby="recommended-title">
      <p className="eyebrow">{picks.reason ? EYEBROW[picks.reason] : 'Recommended'}</p>
      <h2 id="recommended-title" className="mt-2 text-3xl font-bold">
        {picks.reason ? 'Recommended for you' : 'Recommended picks'}
      </h2>
      <div className={`mt-6 grid grid-cols-2 gap-3 transition-opacity duration-200 md:grid-cols-4 md:gap-4 ${fading ? 'opacity-0' : 'opacity-100'}`}>
        {picks.products.map((p) => (
          <Reveal key={p.slug} stagger repeat className="flex">
            <Link href={`/products/${p.slug}`} className="card group flex w-full flex-col overflow-hidden transition-shadow hover:shadow-lg">
              <div className="relative aspect-[4/3] overflow-hidden bg-paper">
                {p.image ? (
                  <CardImage src={p.image} alt={p.name} />
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
        ))}
      </div>
    </section>
  );
}
