'use client';
// "Recommended" on the home page.
// - The server renders real products (a mix across categories, what a first-time visitor sees), so
//   Google and no-JS visitors get product names and links (public pages stay server-rendered).
// - After loading, a returning visitor gets personal picks from what they opened or put in their
//   enquiry list (useHistory, kept in their browser only): swapped in at once if the section is off
//   screen, with a short fade if it is already in view.
// - Later changes (a quick view, the enquiry list, another tab, back/forward) are applied only while
//   the section is off screen, so nothing reshuffles under the visitor's eyes.
// - Always the same number of cards (recommend() tops up), so nothing below ever jumps.
import { useEffect, useRef, useState } from 'react';
import Reveal from '@/components/public/Reveal';
import { recommend, useHistory, type Reason } from '@/lib/history';
import { useCatalogue } from './CatalogueContext';
import HomeProductCard from './HomeProductCard';

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
  const { viewed, listed, ready } = useHistory();
  const section = useRef<HTMLElement>(null);
  const onScreen = useRef(false);
  const pending = useRef<Picks | null>(null);
  const personalised = useRef(false);
  const [picks, setPicks] = useState<Picks>(() => recommend(products, [], [], COUNT));
  const [fading, setFading] = useState(false);
  // What is on screen, kept in step with every change (compared against before any update)
  const shown = useRef(picks);
  const show = (next: Picks) => {
    shown.current = next;
    setPicks(next);
  };

  // Section visibility: a change that waited while it was on screen is applied once it leaves
  useEffect(() => {
    const el = section.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      onScreen.current = e.isIntersecting;
      if (!e.isIntersecting && pending.current) {
        show(pending.current);
        pending.current = null;
      }
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // History changed (or was read for the first time): work out the picks
  useEffect(() => {
    if (!ready) return;
    const next = recommend(products, viewed, listed, COUNT);
    const first = !personalised.current;
    personalised.current = true; // the first load is over, whatever it found (also with no history)
    if (same(next, shown.current)) { // nothing really changed: no update, no re-render
      pending.current = null;
      return;
    }
    if (first) {
      // First load: swap in at once; fade only if the section is already on screen
      const r = section.current?.getBoundingClientRect();
      if (!r || r.bottom <= 0 || r.top >= window.innerHeight) return show(next);
      setFading(true);
      const timer = window.setTimeout(() => { show(next); setFading(false); }, FADE_MS);
      // Interrupted before the timer fired (re-run, unmount): apply now, so the grid never stays faded
      return () => { window.clearTimeout(timer); show(next); setFading(false); };
    }
    // Later changes: only while the section is off screen (else they wait for it to leave)
    if (onScreen.current) pending.current = next;
    else { pending.current = null; show(next); }
  }, [ready, viewed, listed, products]);

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
            <HomeProductCard p={p} />
          </Reveal>
        ))}
      </div>
    </section>
  );
}
