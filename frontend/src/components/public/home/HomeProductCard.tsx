// The product card used on the home page (product range and Recommended), so both always look the same:
// picture, category, name (links to the product page) and pack sizes.
// - onQuickView (product range): the picture opens the quick view; children add item numbers and
//   buttons under the text.
// - without it (Recommended): the WHOLE card opens the product page. The name's link is stretched over
//   the card (an invisible ::after layer), so there is still one link for keyboards and screen readers.
// - overlay: badges drawn over the picture.
import Link from 'next/link';
import type { HomeProduct } from '@/lib/catalogue';
import CardImage from './CardImage';

type Props = { p: HomeProduct; onQuickView?: () => void; overlay?: React.ReactNode; children?: React.ReactNode };

export default function HomeProductCard({ p, onQuickView, overlay, children }: Props) {
  const picture = (
    <>
      {p.image ? (
        <CardImage src={p.image} alt={p.name} />
      ) : (
        <span className="absolute inset-0 flex items-center justify-center text-xs text-slate-400">{p.categoryName}</span>
      )}
      {overlay}
    </>
  );
  const box = 'relative block aspect-[4/3] overflow-hidden bg-paper';
  const wholeCard = !onQuickView;
  return (
    <article className="card group relative flex w-full flex-col overflow-hidden transition-shadow hover:shadow-lg">
      {onQuickView ? (
        <button onClick={onQuickView} className={box} aria-label={`Quick view: ${p.name}`}>{picture}</button>
      ) : (
        <div className={box}>{picture}</div>
      )}
      <div className="flex flex-1 flex-col p-3 md:p-4">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-gold-dark">{p.categoryName}</p>
        <Link
          href={`/products/${p.slug}`}
          className={`mt-1 line-clamp-1 font-semibold text-slate-900 ${
            wholeCard ? 'after:absolute after:inset-0 after:content-[""] group-hover:text-forest' : 'hover:text-forest'
          }`}
        >
          {p.name}
        </Link>
        <p className="mt-1 line-clamp-1 text-xs text-slate-500">{p.packFormats}</p>
        {children}
      </div>
    </article>
  );
}
