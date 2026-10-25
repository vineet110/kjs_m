// P6: Partner programme. Agents, brokers, forwarders and distributors apply to refer buyers.
// The partner dashboard and commissions come in Stage 2.
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import PartnerForm from '@/components/public/PartnerForm';
import { features, texts } from '@/lib/api';

export const metadata: Metadata = {
  title: 'Partner programme',
  description: 'Agents, brokers, freight forwarders and distributors: refer buyers to KJS India.',
};

const BENEFITS = [
  { t: 'Your own referral link', d: 'Every buyer you send is tracked to you.' },
  { t: 'Commission on orders', d: 'Earn on confirmed orders from buyers you refer (terms agreed with our team).' },
  { t: 'A real factory behind you', d: 'Stick packs, blending, packaging and warehousing in Hyderabad, FSSC 22000 certified.' },
];

export default async function PartnersPage() {
  const [f, t] = await Promise.all([features(), texts()]);
  if (!f.partners) notFound();
  return (
    <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 md:grid-cols-5">
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
  );
}
