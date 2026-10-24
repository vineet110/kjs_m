// Offers ticker (P1): a thin scrolling strip of live offers set in Admin > Website.
// Hidden when there are no live offers or the feature is switched off (config/features.ini).
import Link from 'next/link';
import { serverGet, type Offer } from '@/lib/api';

export default async function OffersTicker() {
  const offers = (await serverGet<Offer[]>('/public/offers').catch(() => null)) ?? [];
  if (offers.length === 0) return null;
  const items = [...offers, ...offers]; // doubled so the scroll loops without a gap
  return (
    <div className="overflow-hidden bg-gold text-ink" aria-label="Current offers">
      <div className="flex w-max animate-ticker gap-12 whitespace-nowrap py-1.5 text-sm font-semibold hover:[animation-play-state:paused] motion-reduce:animate-none">
        {items.map((o, i) =>
          o.link ? (
            <Link key={i} href={o.link} className="underline-offset-2 hover:underline">★ {o.text}</Link>
          ) : (
            <span key={i}>★ {o.text}</span>
          ),
        )}
      </div>
    </div>
  );
}
