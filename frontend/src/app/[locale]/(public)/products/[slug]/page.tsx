// P3: Product page. Prices are not shown until KJS approves them (backlog I3 / D19).
import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { JsonLd } from '@/components/public/JsonLd';
import GatedActions from '@/components/public/GatedActions';
import TrackView from '@/components/public/TrackView';
import { features, serverGet, type Product, type PublicFile } from '@/lib/api';
import { imageOf, summary } from '@/lib/catalogue';
import { SITE } from '@/lib/site';

// Next 15+: params arrive as a Promise.
type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const p = await serverGet<Product>(`/public/products/${encodeURIComponent(slug)}`);
  return p ? { title: p.name, description: summary(p.description).slice(0, 160) } : {};
}

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;
  const p = await serverGet<Product>(`/public/products/${encodeURIComponent(slug)}`);
  if (!p) notFound();
  const [files, f] = await Promise.all([serverGet<PublicFile[]>(`/public/products/${p.slug}/files`).catch(() => null), features()]);
  const photos = (files ?? []).filter((x) => x.content_type.startsWith('image/'));
  const docs = (files ?? []).filter((x) => !x.content_type.startsWith('image/'));
  const ownImage = imageOf(p);
  const mainImage = ownImage || photos[0]?.url;

  const facts = [
    ['Category', p.category_name],
    ['Pack formats', p.pack_formats || 'On request'],
    ['Minimum order', p.moq || 'On request'],
    ['Private label', p.private_label ? 'Available' : 'No'],
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-12">
      <TrackView slug={p.slug} />
      <JsonLd
        data={{
          '@context': 'https://schema.org',
          '@type': 'Product',
          name: p.name,
          description: summary(p.description),
          category: p.category_name,
          brand: { '@type': 'Organization', name: 'KJS India' },
        }}
      />
      <nav className="text-sm text-slate-500">
        <Link href="/products" className="hover:text-slate-900">Products</Link> /{' '}
        <Link href={`/categories/${p.category_slug}`} className="hover:text-slate-900">{p.category_name}</Link> /{' '}
        <span className="text-slate-900">{p.name}</span>
      </nav>
      <div className="grid gap-8 md:grid-cols-2">
        <div className="card relative flex aspect-square items-center justify-center overflow-hidden bg-paper">
          {mainImage ? (
            <Image src={mainImage} alt={p.name} fill className="object-contain" sizes="(max-width: 768px) 100vw, 50vw" unoptimized={!ownImage} />
          ) : (
            <span className="text-slate-400">{p.category_name}</span>
          )}
        </div>
        <div className="space-y-5">
          <div className="flex gap-2">
            <span className="rounded bg-gold/15 px-2 py-0.5 text-xs font-semibold text-gold-dark">{p.category_name}</span>
            {p.private_label && <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">Available with your brand</span>}
          </div>
          <h1 className="text-3xl font-bold">{p.name}</h1>
          <p className="text-sm text-slate-500">Made in Hyderabad, India</p>
          {p.description && <p className="whitespace-pre-line text-slate-700">{p.description}</p>}
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-slate-200">
            {facts.map(([k, v]) => (
              <div key={k} className="bg-white p-3">
                <dt className="text-xs font-semibold uppercase text-slate-500">{k}</dt>
                <dd className="text-sm font-medium">{v}</dd>
              </div>
            ))}
          </dl>
          {f.gated_actions && <GatedActions productSlug={p.slug} productName={p.name} />}
          {docs.length > 0 && (
            <ul className="text-sm">
              {docs.map((d) => <li key={d.id}><a href={d.url} className="underline">{d.name}</a></li>)}
            </ul>
          )}
          <div className="flex flex-wrap gap-3">
            <a href={`${SITE.whatsapp}?text=${encodeURIComponent(`Hi, I'm interested in ${p.name}.`)}`} target="_blank" rel="noopener" className="btn-ghost">
              WhatsApp sales
            </a>
          </div>
          <p className="text-xs text-slate-500">No online payment. Our sales team replies with a quote.</p>
        </div>
      </div>
    </div>
  );
}
