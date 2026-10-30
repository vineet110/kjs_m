import type { Metadata } from 'next';
import CategoryGrid from '@/components/public/CategoryGrid';
import EnquiryButton from '@/components/public/EnquiryButton';
import ProductCard from '@/components/public/ProductCard';
import Reveal from '@/components/public/Reveal';
import { serverGet, type Category, type Product } from '@/lib/api';

export const metadata: Metadata = { title: 'Products' };

export default async function ProductsPage() {
  const [categories, products] = await Promise.all([
    serverGet<Category[]>('/public/categories'),
    serverGet<Product[]>('/public/products'),
  ]);

  return (
    <div className="mx-auto max-w-7xl space-y-10 px-4 py-12">
      <div>
        <p className="eyebrow">Products</p>
        <h1 className="mt-2 text-3xl font-bold">Our product range</h1>
        <p className="mt-2 text-slate-600">Choose a category, or ask us for the full catalogue.</p>
      </div>
      <CategoryGrid categories={categories ?? []} />
      {products && products.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Cards pop in, row by row, every time they scroll into view (down or up) */}
          {products.map((p) => (
            <Reveal key={p.id} stagger repeat className="flex">
              <ProductCard p={p} />
            </Reveal>
          ))}
        </div>
      ) : (
        <div className="card flex flex-col items-start gap-3 p-6">
          <p className="font-semibold">Our detailed product list is being published.</p>
          <p className="text-sm text-slate-600">Tell us what you need and we will send the catalogue and price sheet.</p>
          <EnquiryButton label="Request catalogue" source="price_sheet" title="Request our catalogue" />
        </div>
      )}
    </div>
  );
}
