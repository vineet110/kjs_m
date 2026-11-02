'use client';
import { useState } from 'react';
import { api, ApiFailure } from '@/lib/api';
import { PARTNER_TYPES } from '@/lib/partners';

export default function PartnerForm() {
  const [state, setState] = useState<'idle' | 'sending' | 'done'>('idle');
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    setState('sending');
    setError('');
    try {
      await api('/public/partners', { method: 'POST', body: { ...f, consent: f.consent === 'on' } });
      setState('done');
    } catch (err) {
      setError(err instanceof ApiFailure ? err.message : 'Could not send. Please email us instead.');
      setState('idle');
    }
  }

  if (state === 'done') {
    return <div className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-900"><p className="font-semibold">Thank you for applying!</p><p>Our partnerships team will contact you soon.</p></div>;
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <h2 className="text-lg font-bold">Apply to become a partner</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="label" htmlFor="p-name">Full name *</label><input id="p-name" name="name" required minLength={2} className="input" /></div>
        <div><label className="label" htmlFor="p-company">Company</label><input id="p-company" name="company" className="input" /></div>
        <div>
          <label className="label" htmlFor="p-type">You are a *</label>
          <select id="p-type" name="partner_type" required className="input">{PARTNER_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        </div>
        <div><label className="label" htmlFor="p-country">Country *</label><input id="p-country" name="country" required minLength={2} className="input" /></div>
        <div><label className="label" htmlFor="p-email">Email *</label><input id="p-email" name="email" type="email" required className="input" /></div>
        <div><label className="label" htmlFor="p-phone">Phone / WhatsApp</label><input id="p-phone" name="phone" className="input" /></div>
      </div>
      <div><label className="label" htmlFor="p-message">Which markets and buyers do you work with?</label><textarea id="p-message" name="message" rows={3} className="input" /></div>
      <input name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />
      <label className="flex items-start gap-2 text-xs text-slate-600">
        <input type="checkbox" name="consent" required className="mt-0.5" />
        <span>I agree that KJS India may contact me about the partner programme and store my details for that purpose.</span>
      </label>
      {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      <button disabled={state === 'sending'} className="btn-gold w-full">{state === 'sending' ? 'Sending…' : 'Apply'}</button>
    </form>
  );
}
