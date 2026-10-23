'use client';
// The "gate" (backlog D3): visitors browse freely; this form appears only when they
// ask for something (price sheet, sample, quote). Every submission becomes a lead.
import { useState } from 'react';
import { api, ApiFailure } from '@/lib/api';

type Props = {
  source?: 'enquiry_form' | 'price_sheet';
  productSlug?: string;
  categorySlug?: string;
  title?: string;
  onDone?: () => void;
};

const BUYER_TYPES = ['Brand / private label', 'Distributor', 'Retailer', 'Importer', 'Other'];

export default function EnquiryForm({ source = 'enquiry_form', productSlug, categorySlug, title, onDone }: Props) {
  const [state, setState] = useState<'idle' | 'sending' | 'done'>('idle');
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const email = String(f.get('email') || '').trim();
    setState('sending');
    setError('');
    try {
      await api('/public/leads', {
        method: 'POST',
        body: {
          source,
          name: f.get('name'),
          company: f.get('company'),
          email: email || null,
          phone: f.get('phone'),
          country: f.get('country'),
          buyer_type: f.get('buyer_type'),
          quantity: f.get('quantity'),
          message: f.get('message'),
          consent: f.get('consent') === 'on',
          website: f.get('website'), // honeypot
          product_slug: productSlug,
          category_slug: categorySlug,
          source_page: window.location.pathname,
        },
      });
      setState('done');
    } catch (err) {
      setError(err instanceof ApiFailure ? err.message : 'Could not send. Please WhatsApp us instead.');
      setState('idle');
    }
  }

  if (state === 'done') {
    return (
      <div className="space-y-3 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-900">
        <p className="font-semibold">Thank you! We have your request.</p>
        <p>Our sales team will contact you soon, usually within one working day (Mon–Sat).</p>
        {onDone && <button onClick={onDone} className="btn-ghost">Close</button>}
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      {title && <h3 className="text-lg font-bold">{title}</h3>}
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="label" htmlFor="name">Full name *</label><input id="name" name="name" required minLength={2} className="input" /></div>
        <div><label className="label" htmlFor="company">Company</label><input id="company" name="company" className="input" /></div>
        <div><label className="label" htmlFor="email">Work email</label><input id="email" name="email" type="email" className="input" /></div>
        <div><label className="label" htmlFor="phone">Phone / WhatsApp</label><input id="phone" name="phone" className="input" placeholder="+..." /></div>
        <div><label className="label" htmlFor="country">Country</label><input id="country" name="country" className="input" /></div>
        <div>
          <label className="label" htmlFor="buyer_type">You are</label>
          <select id="buyer_type" name="buyer_type" className="input">
            {BUYER_TYPES.map((b) => <option key={b}>{b}</option>)}
          </select>
        </div>
      </div>
      <div><label className="label" htmlFor="quantity">Quantity needed</label><input id="quantity" name="quantity" className="input" placeholder="e.g. 50,000 sticks / month" /></div>
      <div><label className="label" htmlFor="message">Message</label><textarea id="message" name="message" rows={3} className="input" /></div>
      {/* Honeypot: hidden from people, bots fill it in */}
      <input name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />
      <label className="flex items-start gap-2 text-xs text-slate-600">
        <input type="checkbox" name="consent" required className="mt-0.5" />
        <span>I agree that KJS India may contact me about this request and store my details for that purpose (DPDP Act 2023).</span>
      </label>
      <p className="text-xs text-slate-500">Please give an email or a phone number.</p>
      {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      <button disabled={state === 'sending'} className="btn-gold w-full">
        {state === 'sending' ? 'Sending…' : source === 'price_sheet' ? 'Request price sheet' : 'Send enquiry'}
      </button>
    </form>
  );
}
