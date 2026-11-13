'use client';
// Lead Management > Internal lead: leads staff type in themselves (a phone call, a trade fair, a walk-in).
// A lead you add is yours from the start; it then works like any other lead (status, notes, tasks, SLA).
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { uploadFiles } from '@/components/portal/FileList';
import { Icon } from '@/components/portal/icons';
import { useCallback, useEffect, useState } from 'react';
import LeadSourceList, { useSourceLeads } from '@/components/portal/LeadSourceList';
import { Msg, PageTitle } from '@/components/portal/ui';
import { PhoneInput } from '@/components/public/CountryPicker';
import { api, ApiFailure, type Category, type Lead } from '@/lib/api';
import LoadError from '@/components/ui/LoadError';

export default function InternalLeadsPage() {
  const { rows, reload, error } = useSourceLeads('internal');
  const [adding, setAdding] = useState(false);
  return (
    <div className="space-y-5">
      <PageTitle title="Internal leads" sub="Leads you met outside the website: a call, a fair, a walk-in.">
        <button type="button" onClick={() => setAdding(!adding)} className="btn-dark">{adding ? 'Close' : '+ Add lead'}</button>
      </PageTitle>
      {adding && <AddLead />}
      <LeadSourceList rows={rows} error={error} onRetry={reload} empty={{ title: 'No internal leads yet', text: 'Use "+ Add lead" to type in a buyer you spoke to.' }} />
    </div>
  );
}

function AddLead() {
  const router = useRouter();
  const [cats, setCats] = useState<Category[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [savedId, setSavedId] = useState<number | null>(null); // saved, but a file failed: show the way to the lead
  const loadCats = useCallback(() => {
    setLoadErr(null);
    api<Category[]>('/public/categories').then(setCats).catch(setLoadErr);
  }, []);
  useEffect(() => {
    loadCats();
  }, [loadCats]);

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
      // Files go after the lead exists (they hang on its id). A failed file doesn't undo the lead:
      // we say which ones failed and the lead's Files tab takes them again.
      const failed = await uploadFiles('lead', String(lead.id), files);
      if (failed.length) {
        setSavedId(lead.id);
        setMsg({ ok: false, text: `Lead saved, but some files did not upload. ${failed.join(' ')}` });
        setBusy(false);
        return;
      }
      router.push(`/employee/contacts/${lead.id}`); // straight to the new lead, ready to work on
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save the lead.' });
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="card space-y-4 p-5">
      {loadErr != null && <LoadError error={loadErr} onRetry={loadCats} />}
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
      <div>
        <span className="label">Files</span>
        {/* The browser's own file button looks out of place, so it is hidden and this box opens it.
            No `name`: the files are sent one by one after the lead is saved, not with the form. */}
        <label htmlFor="il-files"
          className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-slate-300 bg-white px-4 py-3 text-sm text-slate-500 hover:border-slate-400 hover:bg-slate-50 focus-within:ring-2 focus-within:ring-orange-300">
          <Icon name="file" className="h-5 w-5 shrink-0 text-slate-400" />
          <span className="min-w-0 flex-1 truncate">
            {files.length ? files.map((f) => f.name).join(', ') : 'Add visiting cards, price lists, photos…'}
          </span>
          <span className="shrink-0 rounded-md border border-slate-300 bg-white px-3 py-1 font-medium text-slate-700">
            {files.length ? `${files.length} chosen · Change` : 'Choose files'}
          </span>
          <input id="il-files" type="file" multiple className="sr-only"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
        </label>
      </div>
      <Msg msg={msg} />
      {savedId != null
        ? <Link href={`/employee/contacts/${savedId}`} className="btn-dark inline-block">Open the lead</Link>
        : <button disabled={busy} className="btn-dark">{busy ? 'Saving…' : 'Save lead'}</button>}
    </form>
  );
}
