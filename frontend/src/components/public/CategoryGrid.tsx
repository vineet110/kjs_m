import Link from 'next/link';
import type { Category } from '@/lib/api';

const TONES = [
  'from-[#5B3420] to-[#2E1A10]',
  'from-[#2F6B3A] to-[#173A1F]',
  'from-[#C2631F] to-[#7A3A0E]',
  'from-[#B3242F] to-[#6A1219]',
];

export default function CategoryGrid({ categories }: { categories: Category[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {categories.map((c, i) => (
        <Link
          key={c.slug}
          href={`/categories/${c.slug}`}
          className={`group flex min-h-40 flex-col justify-between rounded-xl bg-gradient-to-br p-5 text-white shadow-sm transition-transform hover:-translate-y-0.5 ${TONES[i % TONES.length]}`}
        >
          <span className="text-xs font-semibold uppercase tracking-widest text-white/70">
            {c.product_count ? `${c.product_count} products` : 'Catalogue on request'}
          </span>
          <div>
            <h3 className="text-2xl font-bold">{c.name}</h3>
            <p className="mt-1 line-clamp-2 text-sm text-white/80">{c.description}</p>
          </div>
        </Link>
      ))}
    </div>
  );
}
