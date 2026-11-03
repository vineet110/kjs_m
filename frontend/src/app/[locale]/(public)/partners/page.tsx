// P6: Partner programme. Sales agents, referral partners, forwarders and distributors apply to refer buyers.
// The partner dashboard and commissions come in Stage 2. Real content only: no commission numbers or
// testimonials until KJS gives real ones (backlog A47).
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import PartnerForm from '@/components/public/PartnerForm';
import { features, serverGet, texts, type Category } from '@/lib/api';
import { partnerLabel, type PartnerType } from '@/lib/partners';

export const metadata: Metadata = {
  title: 'Partner programme',
  description: 'Sales agents, referral partners, freight forwarders and distributors: refer buyers to KJS India.',
};

const BENEFITS = [
  { t: 'Commission on orders', d: 'Earn on confirmed orders from buyers you refer (terms agreed with our team).' },
  { t: 'A real factory behind you', d: 'Stick packs, blending, packaging and warehousing in Hyderabad, FSSC 22000 certified.' },
];

// Who can apply: the partner types in the form, with what each one does
const WHO: { type: PartnerType; d: string }[] = [
  { type: 'agent', d: 'You sell to retailers, distributors or brands in your market.' },
  { type: 'broker', d: 'You know buyers who need a manufacturer and introduce them to us.' },
  { type: 'forwarder', d: 'You ship for importers and can point them to a supplier.' },
  { type: 'distributor', d: 'You buy and resell food and drink products in your region.' },
];

// The steps people really go through today (the form, then our partnerships team)
const STEPS = [
  { t: 'Apply', d: 'Fill in the form on this page.' },
  { t: 'We contact you', d: 'Our partnerships team gets in touch to understand your markets and buyers.' },
  { t: 'Agree the terms', d: 'Commission and how referrals work are agreed with our team, then you start referring buyers.' },
];

export default async function PartnersPage() {
  // A failed categories list only hides that section: the form must always show
  const [f, t, categories] = await Promise.all([features(), texts(), serverGet<Category[]>('/public/categories').catch(() => null)]);
  if (!f.partners) notFound();
  // Only categories with products in the catalogue (none shown if the list didn't load)
  const stocked = (categories ?? []).filter((c) => c.product_count > 0);
  return (
    <div className="mx-auto max-w-7xl space-y-14 px-4 py-12">
      <div className="grid gap-10 md:grid-cols-5">
        <div className="space-y-5 md:col-span-2">
          <p className="eyebrow">Partner programme</p>
          <h1 className="text-3xl font-bold">Grow with KJS India</h1>
          <p className="text-slate-600">{t['partners.intro'] ?? 'Refer buyers to KJS India and grow with us.'}</p>
          <ul className="space-y-3">
            {BENEFITS.map((b) => (
              <li key={b.t} className="card p-4">
                <p className="font-semibold">{b.t}</p>
                <p className="text-sm text-slate-600">{b.d}</p>
              </li>
            ))}
          </ul>
        </div>
        <div className="card p-6 md:col-span-3">
          <PartnerForm />
        </div>
      </div>

      <section>
        <h2 className="text-2xl font-bold">Who can apply</h2>
        <ul className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {WHO.map((w) => (
            <li key={w.type} className="card p-4">
              <p className="font-semibold">{partnerLabel(w.type)}</p>
              <p className="mt-1 text-sm text-slate-600">{w.d}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-2xl font-bold">How it works</h2>
        <ol className="mt-5 grid gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.t} className="rounded-xl border border-slate-200 bg-paper p-5">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gold text-sm font-extrabold text-ink">{i + 1}</span>
              <h3 className="mt-3 font-semibold">{s.t}</h3>
              <p className="mt-1 text-sm text-slate-600">{s.d}</p>
            </li>
          ))}
        </ol>
      </section>

      {stocked.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold">What your buyers can order</h2>
          <p className="mt-1 text-slate-600">Our current catalogue, for private label and export.</p>
          <ul className="mt-5 flex flex-wrap gap-2">
            {stocked.map((c) => (
              <li key={c.slug}>
                <Link href={`/categories/${c.slug}`} className="inline-block rounded-full bg-paper px-4 py-2 text-sm font-semibold hover:bg-gold-light/50">
                  {c.name} <span className="font-normal text-slate-500">({c.product_count})</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
