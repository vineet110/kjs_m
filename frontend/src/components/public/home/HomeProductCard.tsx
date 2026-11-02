// The product card used on the home page (product range and Recommended), so both always look the same:
// picture, category, name (links to the product page) and pack sizes.
// - onQuickView (product range): the picture opens the quick view; children add item numbers and
//   buttons under the text.
// - without it (Recommended): the WHOLE card opens the product page. The name's link is stretched over
//   the card (an invisible ::after layer), so there is still one link for keyboards and screen readers.
// - overlay: badges drawn over the picture. topLeft: badges stacked under the offer badge ("Up to X% OFF",
//   when set) in one top-left column, so they never overlap whatever their size.
// Every card has the same height (fixed picture box; category, name and pack sizes always one line: a
// name is required, and an empty category or pack sizes keeps its line), so swapping cards never changes
// the page's height (Safari has no scroll anchoring).
import Link from 'next/link';
import OfferBadge from '@/components/public/OfferBadge';
import { offerLabel, type HomeProduct } from '@/lib/catalogue';
import CardImage from './CardImage';

type Props = { p: HomeProduct; onQuickView?: () => void; overlay?: React.ReactNode; topLeft?: React.ReactNode; children?: React.ReactNode };

export default function HomeProductCard({ p, onQuickView, overlay, topLeft, children }: Props) {
  const offer = offerLabel(p.offerPercent);
  const picture = (
    <>
      {p.image ? (
        <CardImage src={p.image} alt={p.name} />
      ) : (
        <span className="absolute inset-0 flex items-center justify-center text-xs text-slate-400">{p.categoryName}</span>
      )}
      <span className="absolute left-2 top-2 flex flex-col items-start gap-1">
        <OfferBadge percent={p.offerPercent} />
        {topLeft}
      </span>
      {overlay}
    </>
  );
  const box = 'relative block aspect-[4/3] overflow-hidden bg-paper';
  const wholeCard = !onQuickView;
  return (
    <article className="card group relative flex w-full flex-col overflow-hidden transition-shadow hover:shadow-lg">
      {onQuickView ? (
        <button onClick={onQuickView} className={box} aria-label={`Quick view: ${p.name}${offer ? `, ${offer}` : ''}`}>{picture}</button>
      ) : (
        <div className={box}>{picture}</div>
      )}
      <div className="flex flex-1 flex-col p-3 md:p-4">
        <p className="line-clamp-1 text-[11px] font-semibold uppercase tracking-wide text-gold-dark">{p.categoryName || ' '}</p>
        <Link
          href={`/products/${p.slug}`}
          className={`mt-1 line-clamp-1 font-semibold text-slate-900 ${
            wholeCard ? 'after:absolute after:inset-0 after:content-[""] group-hover:text-forest' : 'hover:text-forest'
          }`}
        >
          {p.name}
        </Link>
        <p className="mt-1 line-clamp-1 text-xs text-slate-500">{p.packFormats || ' '}</p>
        {children}
      </div>
    </article>
  );
}
