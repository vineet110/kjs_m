// Category cards on the Products page: a picture, the name, and a few small animations.
// - Picture: a fixed one for categories that have it (CATEGORY_IMAGES), else the first product picture of
//   that category (`images`, from the products page), else just the coloured background.
// - Animations: cards pop in as they scroll into view (Reveal); on hover the picture zooms slowly, a gold
//   shine sweeps across and "Explore" slides in; the Coffee card has steam rising. All motion-safe: nothing
//   moves for visitors who turned on "reduce motion".
import Image from 'next/image';
import Link from 'next/link';
import Reveal from '@/components/public/Reveal';
import type { Category } from '@/lib/api';

const TONES = [
  'from-[#5B3420] to-[#2E1A10]',
  'from-[#2F6B3A] to-[#173A1F]',
  'from-[#C2631F] to-[#7A3A0E]',
  'from-[#B3242F] to-[#6A1219]',
];

// Category pictures kept in frontend/public/images/categories. Coffee and health drinks (hot chocolate):
// cut from the coffee catalogue PDF. Confectionery: three KJS packs from the confectionery catalogue.
// Tea: a drawn cup until KJS sends a tea photo.
const CATEGORY_IMAGES: Record<string, string> = {
  coffee: '/images/categories/coffee.jpg',
  tea: '/images/categories/tea.jpg',
  'health-drinks': '/images/categories/health-drinks.jpg',
  confectionery: '/images/categories/confectionery.jpg',
};

/** Three soft white wisps rising over the Coffee card. */
function Steam() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute right-8 top-6 hidden h-24 w-16 motion-safe:block">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="absolute bottom-0 h-10 w-3 rounded-full bg-white/50 blur-[6px] animate-steam"
          style={{ left: `${i * 18}px`, animationDelay: `${i * 0.9}s` }}
        />
      ))}
    </div>
  );
}

export default function CategoryGrid({ categories, images = {} }: { categories: Category[]; images?: Record<string, string> }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {categories.map((c, i) => {
        const image = CATEGORY_IMAGES[c.slug] ?? images[c.slug];
        return (
          <Reveal key={c.slug} stagger repeat className="flex">
            <Link
              href={`/categories/${c.slug}`}
              className={`group relative flex min-h-48 w-full flex-col justify-between overflow-hidden rounded-xl bg-gradient-to-br p-5 text-white shadow-sm transition duration-300 hover:shadow-xl motion-safe:hover:-translate-y-1 ${TONES[i % TONES.length]}`}
            >
              {image && (
                <>
                  <Image
                    src={image}
                    alt=""
                    fill
                    sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
                    className="object-cover opacity-60 transition-transform duration-700 ease-out motion-safe:group-hover:scale-110"
                  />
                  {/* Keeps the text readable on any picture */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/40 to-black/10" />
                </>
              )}
              {c.slug === 'coffee' && <Steam />}
              {/* Gold shine that sweeps across on hover */}
              <div
                aria-hidden="true"
                className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 -skew-x-12 bg-gradient-to-r from-transparent via-gold-light/25 to-transparent opacity-0 group-hover:opacity-100 motion-safe:group-hover:animate-shine"
              />
              <span className="relative text-xs font-semibold uppercase tracking-widest text-white/80">
                {c.product_count ? `${c.product_count} products` : 'Catalogue on request'}
              </span>
              <div className="relative">
                <h3 className="text-2xl font-bold">{c.name}</h3>
                <p className="mt-1 line-clamp-2 text-sm text-white/85">{c.description}</p>
                <span className="mt-2 inline-block text-sm font-semibold text-gold-light opacity-0 transition duration-300 group-hover:opacity-100 motion-safe:translate-x-[-8px] motion-safe:group-hover:translate-x-0">
                  Explore →
                </span>
              </div>
            </Link>
          </Reveal>
        );
      })}
    </div>
  );
}
