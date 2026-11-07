'use client';
// Lead Management > Internal lead: leads staff type in themselves (a phone call, a trade fair, a walk-in).
// A lead you add is yours from the start; it then works like any other lead (status, notes, tasks, SLA).
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import LeadSourceList, { useSourceLeads } from '@/components/portal/LeadSourceList';
import { Msg, PageTitle } from '@/components/portal/ui';
import { PhoneInput } from '@/components/public/CountryPicker';
import { api, ApiFailure, type Category, type Lead } from '@/lib/api';

export default function InternalLeadsPage() {
  const { rows } = useSourceLeads('internal');
  const [adding, setAdding] = useState(false);
  return (
    <div className="space-y-5">
      <PageTitle title="Internal lead" sub="Leads you met outside the website: a call, a fair, a walk-in.">
        <button type="button" onClick={() => setAdding(!adding)} className="btn-dark">{adding ? 'Close' : '+ Add lead'}</button>
      </PageTitle>
      {adding && <AddLead />}
      <LeadSourceList rows={rows} empty={{ title: 'No internal leads yet', text: 'Use "+ Add lead" to type in a buyer you spoke to.' }} />
    </div>
  );
}

function AddLead() {
  const router = useRouter();
  const [cats, setCats] = useState<Category[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api<Category[]>('/public/categories').then(setCats).catch(() => setCats([]));
  }, []);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    setBusy(true);
    setMsg(null);
    try {
      const lead = await api<Lead>('/employee/leads', {
        method: 'POST',
        body: { ...f, email: f.email || null, category_slug: f.category_slug || null },
      });
      router.push(`/employee/contacts/${lead.id}`); // straight to the new lead, ready to work on
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save the lead.' });
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="card space-y-4 p-5">
      <h2 className="font-semibold">New internal lead</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="label" htmlFor="il-name">Name *</label><input id="il-name" name="name" required minLength={2} maxLength={120} className="input" /></div>
        <div><label className="label" htmlFor="il-company">Company</label><input id="il-company" name="company" maxLength={200} className="input" /></div>
        <div><label className="label" htmlFor="il-phone">Phone / WhatsApp *</label><PhoneInput id="il-phone" maxLength={30} /></div>
        <div><label className="label" htmlFor="il-email">Email</label><input id="il-email" name="email" type="email" maxLength={255} className="input" /></div>
        <div><label className="label" htmlFor="il-country">Country</label><input id="il-country" name="country" maxLength={80} className="input" /></div>
        <div>
          <label className="label" htmlFor="il-type">Buyer type</label>
          <select id="il-type" name="buyer_type" className="input" defaultValue="">
            <option value="">Select an option</option>
            {['Distributor', 'Retailer', 'Importer', 'Brand (private label)', 'Other'].map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="il-cat">Interested in</label>
          <select id="il-cat" name="category_slug" className="input" defaultValue="">
            <option value="">Select an option</option>
            {cats.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
          </select>
        </div>
        <div><label className="label" htmlFor="il-qty">Quantity</label><input id="il-qty" name="quantity" maxLength={120} placeholder="e.g. 2 tonnes a month" className="input" /></div>
      </div>
      <div><label className="label" htmlFor="il-msg">What they need</label><textarea id="il-msg" name="message" maxLength={4000} rows={3} className="input" /></div>
      <Msg msg={msg} />
      <button disabled={busy} className="btn-dark">{busy ? 'Saving…' : 'Save lead'}</button>
    </form>
  );
}
