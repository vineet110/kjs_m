import Image from 'next/image';
import Link from 'next/link';
import type { Product } from '@/lib/api';

export default function ProductCard({ p }: { p: Product }) {
  return (
    <Link href={`/products/${p.slug}`} className="card group overflow-hidden transition-shadow hover:shadow-md">
      <div className="relative flex h-40 items-center justify-center bg-slate-100">
        {p.image_path ? (
          <Image src={p.image_path} alt={p.name} fill className="object-cover" sizes="(max-width: 768px) 100vw, 25vw" />
        ) : (
          <span className="text-xs text-slate-400">{p.category_name}</span>
        )}
      </div>
      <div className="space-y-1 p-4">
        <p className="text-xs font-semibold text-gold-dark">{p.category_name}</p>
        <h3 className="font-semibold group-hover:text-forest">{p.name}</h3>
        {p.pack_formats && <p className="text-xs text-slate-500">{p.pack_formats}</p>}
      </div>
    </Link>
  );
}
