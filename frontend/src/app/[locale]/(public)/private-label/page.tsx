// Private label: how it works, what we can do, and the configurator (pick product, pack, quantity,
// market -> send to sales). No price is shown until KJS gives price bands (backlog I3, A23).
import type { Metadata } from 'next';
import Configurator from '@/components/public/Configurator';
import { serverGet, type Product } from '@/lib/api';
import { CAPABILITIES } from '@/lib/site';

export const metadata: Metadata = {
  title: 'Private label',
  description: 'Your brand, our factory: private-label coffee, tea, health drinks and confectionery in stick packs, sachets and pouches.',
};

const STEPS = [
  { t: 'Tell us your product', d: 'Recipe, pack format, quantity and target market.' },
  { t: 'Samples and recipe', d: 'Our R&D team prepares samples and adjusts the recipe with you.' },
  { t: 'Packaging and approvals', d: 'Your artwork on our packs; documents for your market.' },
  { t: 'Production and dispatch', d: 'Made, packed and shipped from Hyderabad.' },
];

export default async function PrivateLabelPage() {
  const products = (await serverGet<Product[]>('/public/products')) ?? [];
  return (
    <div className="mx-auto max-w-7xl space-y-12 px-4 py-12">
      <div className="max-w-3xl space-y-3">
        <p className="eyebrow">Private label</p>
        <h1 className="text-4xl font-bold">Your brand, our factory</h1>
        <p className="text-lg text-slate-600">Coffee, tea, health drinks and confectionery, blended and packed under your label.</p>
      </div>

      <ol className="grid gap-4 md:grid-cols-4">
        {STEPS.map((s, i) => (
          <li key={s.t} className="card p-5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gold font-bold text-ink">{i + 1}</span>
            <p className="mt-3 font-semibold">{s.t}</p>
            <p className="text-sm text-slate-600">{s.d}</p>
          </li>
        ))}
      </ol>

      <section className="grid gap-8 md:grid-cols-5">
        <div className="space-y-3 md:col-span-2">
          <h2 className="text-2xl font-bold">What we can do</h2>
          <ul className="space-y-2 text-sm">
            {CAPABILITIES.map((c) => <li key={c.slug} className="card p-3"><a href={`/capabilities/${c.slug}`} className="font-semibold underline-offset-2 hover:underline">{c.title}</a></li>)}
          </ul>
        </div>
        <div className="card p-6 md:col-span-3">
          <Configurator products={products.filter((p) => p.private_label).map((p) => ({ slug: p.slug, name: p.name, formats: p.pack_formats, category: p.category_name }))} />
        </div>
      </section>
    </div>
  );
}
