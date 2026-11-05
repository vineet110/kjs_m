'use client';
// The "gate" (backlog D3): visitors browse freely; this form appears only when they
// ask for something (price sheet, spec PDF, sample, quote). Every submission becomes a lead.
// "Asked once, then remembered": after the first form the details stay in this browser only
// (localStorage, with the visitor's consent), so the next request is one click.
import { useEffect, useState } from 'react';
import { CountrySelect, PhoneInput } from '@/components/public/CountryPicker';
import { savedPhoneOk } from '@/lib/countries';
import { api, ApiFailure } from '@/lib/api';

export type LeadSource = 'enquiry_form' | 'price_sheet' | 'spec_pdf' | 'sample' | 'quote' | 'configurator';
type Visitor = { name: string; company: string; email: string; phone: string; country: string; buyer_type: string };
const KEY = 'kjs_visitor';

function loadVisitor(): Visitor | null {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || 'null');
    return v && v.name ? v : null;
  } catch {
    return null;
  }
}

const BUTTON: Record<LeadSource, string> = {
  enquiry_form: 'Send enquiry', price_sheet: 'Request price sheet', spec_pdf: 'Get spec sheet',
  sample: 'Request a sample', quote: 'Get a quote', configurator: 'Send to sales',
};

type Props = {
  source?: LeadSource;
  extraMessage?: string; // e.g. the configurator's choices
  productSlug?: string;
  categorySlug?: string;
  title?: string;
  onDone?: () => void;
  onSent?: () => void; // after the lead is saved (e.g. empty the enquiry list)
};

// Same limit as LeadIn.message in the API: extraMessage + the visitor's message must fit in it
const MESSAGE_MAX = 4000;

const BUYER_TYPES = ['Brand / private label', 'Distributor', 'Retailer', 'Importer', 'Other'];

export default function EnquiryForm({ source = 'enquiry_form', extraMessage = '', productSlug, categorySlug, title, onDone, onSent }: Props) {
  const messageRoom = Math.max(0, MESSAGE_MAX - (extraMessage ? extraMessage.length + 1 : 0)); // +1: the line break
  const [state, setState] = useState<'idle' | 'quick' | 'sending' | 'done'>('idle');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState<Visitor | null>(null);
  const [pickedCountry, setPickedCountry] = useState<string | null>(null); // the phone code follows it
  const [phoneAgain, setPhoneAgain] = useState(false); // the remembered phone couldn't be used

  useEffect(() => {
    let v = loadVisitor();
    // A phone remembered before the phone check (e.g. "call me after 6") would be refused by the server:
    // leave it out of the form and ask for the number again (PR #16 review). The saved details are only
    // replaced when a send succeeds, so closing the form without sending doesn't lose anything.
    const badPhone = !!v?.phone && !savedPhoneOk(v.phone);
    if (v && badPhone) v = { ...v, phone: '' };
    setPhoneAgain(badPhone);
    setSaved(v);
    // One-click send only when the server will take it: a valid phone (required since Nov 2026)
    if (v && source !== 'enquiry_form' && !badPhone && v.phone) setState('quick');
  }, [source]);

  function forget() {
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* nothing saved */
    }
    setSaved(null);
    setState('idle');
  }

  async function send(v: Visitor, extra: { quantity?: string; message?: string; website?: string }, remember = true) {
    setState('sending');
    setError('');
    try {
      await api('/public/leads', {
        method: 'POST',
        body: {
          source, ...v, email: v.email || null,
          quantity: extra.quantity ?? '',
          message: [extraMessage, extra.message].filter(Boolean).join('\n'),
          consent: true, website: extra.website ?? '', // honeypot
          product_slug: productSlug, category_slug: categorySlug, source_page: window.location.pathname,
        },
      });
      try {
        if (remember) localStorage.setItem(KEY, JSON.stringify(v));
        else localStorage.removeItem(KEY); // e.g. a shared office computer
      } catch {
        /* private window: just ask again next time */
      }
      setState('done');
      onSent?.();
    } catch (err) {
      setError(err instanceof ApiFailure ? err.message : 'Could not send. Please WhatsApp us instead.');
      setState('idle');
    }
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (f.get('consent') !== 'on') return setError('Please agree to be contacted.');
    const get = (k: string) => String(f.get(k) || '').trim();
    await send(
      { name: get('name'), company: get('company'), email: get('email'), phone: get('phone'), country: get('country'), buyer_type: get('buyer_type') },
      { quantity: get('quantity'), message: get('message'), website: get('website') },
      f.get('remember') === 'on',
    );
  }

  if (state === 'quick' && saved) {
    return (
      <div className="space-y-3">
        {title && <h3 className="text-lg font-bold">{title}</h3>}
        <p className="text-sm">We will send this request as <b>{saved.name}</b>{saved.company ? ` (${saved.company})` : ''}, {saved.email || saved.phone}.</p>
        {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button onClick={() => send(saved, {})} className="btn-gold flex-1">{BUTTON[source]}</button>
          <button onClick={() => setState('idle')} className="btn-ghost">Change details</button>
        </div>
        <button onClick={forget} className="text-xs text-slate-500 underline">Not you? Forget my details on this device</button>
      </div>
    );
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
    <form key={saved ? "saved" : "new"} onSubmit={submit} className="space-y-3">
      {title && <h3 className="text-lg font-bold">{title}</h3>}
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="label" htmlFor="name">Full name *</label><input id="name" name="name" defaultValue={saved?.name} required minLength={2} className="input" /></div>
        <div><label className="label" htmlFor="company">Company</label><input id="company" name="company" defaultValue={saved?.company} className="input" /></div>
        <div><label className="label" htmlFor="email">Work email</label><input id="email" name="email" defaultValue={saved?.email} type="email" className="input" /></div>
        <div><label className="label" htmlFor="phone">Phone / WhatsApp *</label><PhoneInput id="phone" defaultValue={saved?.phone} linkedCountry={pickedCountry} />
          {phoneAgain && <p role="alert" className="mt-1 text-xs text-red-600">Please re-enter your phone number.</p>}
        </div>
        <div><label className="label" htmlFor="country">Country</label><CountrySelect id="country" defaultValue={saved?.country} onChange={setPickedCountry} /></div>
        <div>
          <label className="label" htmlFor="buyer_type">You are</label>
          <select id="buyer_type" name="buyer_type" defaultValue={saved?.buyer_type} className="input">
            {BUYER_TYPES.map((b) => <option key={b}>{b}</option>)}
          </select>
        </div>
      </div>
      <div><label className="label" htmlFor="quantity">Quantity needed</label><input id="quantity" name="quantity" className="input" placeholder="e.g. 50,000 sticks / month" /></div>
      <div><label className="label" htmlFor="message">Message</label><textarea id="message" name="message" rows={3} maxLength={messageRoom} className="input" /></div>
      {/* Honeypot: hidden from people, bots fill it in */}
      <input name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />
      <label className="flex items-start gap-2 text-xs text-slate-600">
        <input type="checkbox" name="consent" required defaultChecked={!!saved} className="mt-0.5" />
        <span>I agree that KJS India may contact me about this request and store my details for that purpose (DPDP Act 2023).</span>
      </label>
      <label className="flex items-start gap-2 text-xs text-slate-600">
        <input type="checkbox" name="remember" defaultChecked className="mt-0.5" />
        <span>Remember my details in this browser, so my next request is one click. (Untick on a shared computer.)</span>
      </label>
      {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      <button disabled={state === 'sending'} className="btn-gold w-full">
        {state === 'sending' ? 'Sending…' : BUTTON[source]}
      </button>
    </form>
  );
}
