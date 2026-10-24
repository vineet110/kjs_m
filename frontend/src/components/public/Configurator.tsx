'use client';
// Private-label configurator: the visitor picks product, pack, monthly quantity and market,
// then sends it to sales (a lead with source "configurator"). No price until KJS gives price bands.
import { useState } from 'react';
import EnquiryForm from './EnquiryForm';

type P = { slug: string; name: string; formats: string; category: string };
const PACKS = ['Stick pack', 'Sachet', 'Pouch', 'Jar', 'Bulk bag', 'Not sure yet'];
const QUANTITIES = ['Under 50,000 packs', '50,000 – 200,000 packs', '200,000 – 1 million packs', 'Over 1 million packs'];

export default function Configurator({ products }: { products: P[] }) {
  const [choice, setChoice] = useState({ product: products[0]?.slug ?? '', recipe: '', pack: PACKS[0], quantity: QUANTITIES[0], market: '' });
  const [step, setStep] = useState<'pick' | 'send'>('pick');
  const product = products.find((p) => p.slug === choice.product);
  const set = (k: keyof typeof choice) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setChoice({ ...choice, [k]: e.target.value });

  const summary = [
    `Product: ${product?.name ?? 'Custom / not listed'}`,
    choice.recipe && `Recipe notes: ${choice.recipe}`,
    `Pack: ${choice.pack}`,
    `Quantity per month: ${choice.quantity}`,
    `Market: ${choice.market || 'not given'}`,
  ].filter(Boolean).join('\n');

  if (step === 'send') {
    return (
      <div className="space-y-4">
        <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm">{summary}</pre>
        <EnquiryForm source="configurator" productSlug={product?.slug} extraMessage={summary} title="Send this to sales" />
        <button onClick={() => setStep('pick')} className="text-sm underline">← Change choices</button>
      </div>
    );
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); setStep('send'); }} className="space-y-3">
      <h2 className="text-xl font-bold">Build your product</h2>
      <div>
        <label className="label" htmlFor="c-product">Product</label>
        <select id="c-product" value={choice.product} onChange={set('product')} className="input">
          {products.map((p) => <option key={p.slug} value={p.slug}>{p.name} ({p.category})</option>)}
          <option value="">Something else / custom recipe</option>
        </select>
        {product?.formats && <p className="mt-1 text-xs text-slate-500">Usual formats: {product.formats}</p>}
      </div>
      <div><label className="label" htmlFor="c-recipe">Recipe notes (optional)</label><input id="c-recipe" value={choice.recipe} onChange={set('recipe')} maxLength={300} placeholder="e.g. less sugar, hazelnut flavour" className="input" /></div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div><label className="label" htmlFor="c-pack">Pack</label><select id="c-pack" value={choice.pack} onChange={set('pack')} className="input">{PACKS.map((x) => <option key={x}>{x}</option>)}</select></div>
        <div><label className="label" htmlFor="c-qty">Quantity per month</label><select id="c-qty" value={choice.quantity} onChange={set('quantity')} className="input">{QUANTITIES.map((x) => <option key={x}>{x}</option>)}</select></div>
        <div><label className="label" htmlFor="c-market">Market</label><input id="c-market" value={choice.market} onChange={set('market')} placeholder="e.g. UAE" className="input" /></div>
      </div>
      <p className="rounded-lg bg-gold/10 p-3 text-sm">Indicative price: our sales team sends it with your quote, usually within one working day.</p>
      <button className="btn-gold w-full">Next: send to sales</button>
    </form>
  );
}
