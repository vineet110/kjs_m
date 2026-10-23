// P2: Category page. No gate on browsing (backlog D3): the form only opens on an action.
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import EnquiryButton from '@/components/public/EnquiryButton';
import ProductCard from '@/components/public/ProductCard';
import { serverGet, type Category, type Product } from '@/lib/api';

type Props = { params: { slug: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const c = await serverGet<Category>(`/public/categories/${params.slug}`);
  return c ? { title: `${c.name} contract manufacturing`, description: c.description } : {};
}

export default async function CategoryPage({ params }: Props) {
  const [category, products] = await Promise.all([
    serverGet<Category>(`/public/categories/${params.slug}`),
    serverGet<Product[]>(`/public/products?category=${encodeURIComponent(params.slug)}`),
  ]);
  if (!category) notFound();

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-4 py-12">
      <nav className="text-sm text-slate-500">
        <Link href="/products" className="hover:text-slate-900">Products</Link> / <span className="text-slate-900">{category.name}</span>
      </nav>
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-bold">{category.name}</h1>
          <p className="mt-2 max-w-2xl text-slate-600">{category.description}</p>
        </div>
        <EnquiryButton label="Request price sheet" source="price_sheet" categorySlug={category.slug} title={`${category.name}: request price sheet`} />
      </div>

      {products && products.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {products.map((p) => <ProductCard key={p.id} p={p} />)}
        </div>
      ) : (
        <div className="card p-6 text-sm text-slate-600">
          Products in this category are being added. Request the price sheet and our team will send the full list.
        </div>
      )}
    </div>
  );
}
