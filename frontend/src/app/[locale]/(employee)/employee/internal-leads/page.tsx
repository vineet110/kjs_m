'use client';
// Lead Management > Internal lead: leads staff type in themselves (a phone call, a trade fair, a walk-in).
// A lead you add is yours from the start; it then works like any other lead (status, notes, tasks, SLA).
// "Fill from file" reads an Excel / CSV file into the form (nothing is saved until Save is clicked).
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { uploadFiles } from '@/components/portal/FileList';
import { Icon } from '@/components/portal/icons';
import { useCallback, useEffect, useRef, useState } from 'react';
import LeadSourceList, { useSourceLeads } from '@/components/portal/LeadSourceList';
import { Msg, PageTitle } from '@/components/portal/ui';
import { PhoneInput } from '@/components/public/CountryPicker';
import { api, ApiFailure, upload, type Category, type Lead } from '@/lib/api';
import LoadError from '@/components/ui/LoadError';

const BUYER_TYPES = ['Distributor', 'Retailer', 'Importer', 'Brand (private label)', 'Other']; // same list in lead_reader.py
const NOT_SPECIFIED = 'Not specified'; // shown in a field the file didn't have; saved as empty

type Fields = Record<'name' | 'company' | 'email' | 'phone' | 'country' | 'buyer_type' | 'category_slug' | 'quantity' | 'message', string>;
type FileLead = { fields: Fields; extra: Record<string, string> };
type SamePerson = { count: number; lead_id: number | null };

export default function InternalLeadsPage() {
  const { rows, reload, error } = useSourceLeads('internal');
  const [adding, setAdding] = useState(false);
  return (
    <div className="space-y-5">
      <PageTitle title="Internal leads" sub="Leads you met outside the website: a call, a fair, a walk-in.">
        <button type="button" onClick={() => setAdding(!adding)} className="btn-dark">{adding ? 'Close' : '+ Add lead'}</button>
      </PageTitle>
      {adding && <AddLead onSaved={reload} />}
      <LeadSourceList rows={rows} error={error} onRetry={reload} empty={{ title: 'No internal leads yet', text: 'Use "+ Add lead" to type in a buyer you spoke to.' }} />
    </div>
  );
}

function AddLead({ onSaved }: { onSaved: () => void }) {
  const router = useRouter();
  const form = useRef<HTMLFormElement>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  // Two separate lists, so neither can wipe the other: the file the form was filled from (one at most:
  // filling from another file replaces it) and the extra files picked in the Files box
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [savedId, setSavedId] = useState<number | null>(null); // saved, but a file failed: show the way to the lead
  // Filled from a file: the form is drawn again (new key) with these values; empty ones say "Not specified"
  const [fill, setFill] = useState<FileLead | null>(null);
  const [fillKey, setFillKey] = useState(0);
  const [same, setSame] = useState<SamePerson | null>(null); // this person already has leads: asked before saving
  // "Save as a new enquiry" approves this phone + email only: change either and the check runs again
  const sameOk = useRef<string | null>(null);
  const sameAsked = useRef('');
  const [reading, setReading] = useState(false); // a file is being read: Save waits, so the two never mix
  const loadCats = useCallback(() => {
    setLoadErr(null);
    api<Category[]>('/public/categories').then(setCats).catch(setLoadErr);
  }, []);
  useEffect(() => {
    loadCats();
  }, [loadCats]);

  function applyFileLead(lead: FileLead, source: File) {
    setFill(lead);
    setFillKey((k) => k + 1);
    setSame(null);
    sameOk.current = null;
    setSourceFile(source); // kept on the lead too; a new file replaces the old one
  }

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy || reading) return; // Enter pressed while a file is still being read
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    const who = `${(f.phone ?? '').trim()}|${(f.email ?? '').trim().toLowerCase()}`;
    setBusy(true);
    setMsg(null);
    try {
      // Same phone or email as an existing lead: ask first, so nobody adds the same buyer twice by mistake
      if (sameOk.current !== who) {
        const q = new URLSearchParams({ phone: f.phone ?? '', email: f.email ?? '' });
        const found = await api<SamePerson>(`/employee/leads/same-person?${q}`);
        if (found.count > 0) {
          sameAsked.current = who;
          setSame(found);
          setBusy(false);
          return;
        }
      }
      const lead = await api<Lead>('/employee/leads', {
        method: 'POST',
        body: { ...f, email: f.email || null, category_slug: f.category_slug || null },
      });
      // Files go after the lead exists (they hang on its id). A failed file doesn't undo the lead:
      // we say which ones failed and the lead's Files tab takes them again.
      const failed = await uploadFiles('lead', String(lead.id), sourceFile ? [sourceFile, ...files] : files);
      if (failed.length) {
        setSavedId(lead.id);
        onSaved(); // the lead is in the list now, so nobody adds it a second time
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

  const v = (k: keyof Fields) => fill?.fields[k] ?? '';
  const ph = (k: keyof Fields, normal?: string) => (fill && !fill.fields[k] ? NOT_SPECIFIED : normal);
  const extra = Object.keys(fill?.extra ?? {});

  return (
    <div className="card space-y-4 p-5">
      {loadErr != null && <LoadError error={loadErr} onRetry={loadCats} />}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">New internal lead</h2>
        {savedId == null && <FillFromFile onPick={applyFileLead} disabled={busy} onReading={setReading} />}
      </div>
      {fill && (
        <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          Filled from the file. Please check every field before saving. Fields the file didn&apos;t have say &quot;{NOT_SPECIFIED}&quot;.
          {extra.length > 0 && <> <b>Not saved</b> (no field for these yet): {extra.join(', ')}.</>}
        </div>
      )}
      <form key={fillKey} ref={form} onSubmit={save} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div><label className="label" htmlFor="il-name">Name *</label><input id="il-name" name="name" required minLength={2} maxLength={120} className="input" defaultValue={v('name')} placeholder={ph('name')} /></div>
          <div><label className="label" htmlFor="il-company">Company</label><input id="il-company" name="company" maxLength={200} className="input" defaultValue={v('company')} placeholder={ph('company')} /></div>
          <div><label className="label" htmlFor="il-phone">Phone / WhatsApp *</label><PhoneInput id="il-phone" maxLength={30} defaultValue={v('phone')} placeholder={ph('phone', 'Phone / WhatsApp')} /></div>
          <div><label className="label" htmlFor="il-email">Email</label><input id="il-email" name="email" type="email" maxLength={255} className="input" defaultValue={v('email')} placeholder={ph('email')} /></div>
          <div><label className="label" htmlFor="il-country">Country</label><input id="il-country" name="country" maxLength={80} className="input" defaultValue={v('country')} placeholder={ph('country')} /></div>
          <div>
            <label className="label" htmlFor="il-type">Buyer type</label>
            <select id="il-type" name="buyer_type" className="input" defaultValue={v('buyer_type')}>
              <option value="">{ph('buyer_type', 'Select an option')}</option>
              {BUYER_TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="il-cat">Interested in</label>
            <select id="il-cat" name="category_slug" className="input" defaultValue={v('category_slug')}>
              <option value="">{ph('category_slug', 'Select an option')}</option>
              {cats.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
            </select>
          </div>
          <div><label className="label" htmlFor="il-qty">Quantity</label><input id="il-qty" name="quantity" maxLength={120} placeholder={ph('quantity', 'e.g. 2 tonnes a month')} className="input" defaultValue={v('quantity')} /></div>
        </div>
        <div><label className="label" htmlFor="il-msg">What they need</label><textarea id="il-msg" name="message" maxLength={4000} rows={3} className="input" defaultValue={v('message')} placeholder={ph('message')} /></div>
        <div>
          <span className="label">Files</span>
          {sourceFile && savedId == null && (
            <p className="mb-1 truncate text-sm text-slate-600">From file: <b>{sourceFile.name}</b> (will be attached to the lead)</p>
          )}
          {/* The browser's own file button looks out of place, so it is hidden and this box opens it.
              No `name`: the files are sent after the lead is saved, not with the form. */}
          {/* Once the lead is saved, this form can't send files any more: more go in the lead's Files tab. */}
          <label htmlFor="il-files" aria-disabled={savedId != null}
            className="flex cursor-pointer aria-disabled:cursor-not-allowed aria-disabled:opacity-60 items-center gap-3 rounded-lg border border-dashed border-slate-300 bg-white px-4 py-3 text-sm text-slate-500 hover:border-slate-400 hover:bg-slate-50 focus-within:ring-2 focus-within:ring-orange-300">
            <Icon name="file" className="h-5 w-5 shrink-0 text-slate-400" />
            <span className="min-w-0 flex-1 truncate">
              {savedId != null ? "Add the missing files from the lead's Files tab."
                : files.length ? files.map((f) => f.name).join(', ') : 'Add visiting cards, price lists, photos…'}
            </span>
            {savedId == null && <span className="shrink-0 rounded-md border border-slate-300 bg-white px-3 py-1 font-medium text-slate-700">
              {files.length ? `${files.length} chosen · Change` : 'Choose files'}
            </span>}
            <input id="il-files" type="file" multiple className="sr-only" disabled={savedId != null}
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
          </label>
        </div>
        {same && same.count > 0 && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">
            <p>This person already has {same.count} lead{same.count > 1 ? 's' : ''} (same phone or email).</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {same.lead_id != null && <Link href={`/employee/contacts/${same.lead_id}`} className="btn-ghost py-1">Open the existing lead</Link>}
              <button type="button" className="btn-dark py-1" onClick={() => { sameOk.current = sameAsked.current; setSame(null); form.current?.requestSubmit(); }}>
                Save as a new enquiry
              </button>
            </div>
          </div>
        )}
        <Msg msg={msg} />
        {savedId != null
          ? <Link href={`/employee/contacts/${savedId}`} className="btn-dark inline-block">Open the lead</Link>
          : <button disabled={busy || reading} className="btn-dark">{busy ? 'Saving…' : reading ? 'Reading the file…' : 'Save lead'}</button>}
      </form>
    </div>
  );
}

/** "Fill from file": reads an Excel / CSV file on the server and hands back one lead (the person picks
 *  the row when the file has several). Nothing is saved here. */
function FillFromFile({ onPick, disabled, onReading }: {
  onPick: (lead: FileLead, source: File) => void;
  disabled: boolean; // the lead is being saved: no reading or picking now
  onReading: (reading: boolean) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [reading, setReadingHere] = useState(false);
  const setReading = (r: boolean) => { setReadingHere(r); onReading(r); };
  const [err, setErr] = useState('');
  const [choice, setChoice] = useState<{ leads: FileLead[]; more: boolean; file: File } | null>(null);

  async function read(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setReading(true);
    setErr('');
    setChoice(null);
    try {
      const form = new FormData();
      form.set('file', file);
      const r = await upload<{ leads: FileLead[]; more_rows: boolean }>('/employee/leads/read-file', form);
      if (r.leads.length === 1) onPick(r.leads[0], file);
      else setChoice({ leads: r.leads, more: r.more_rows, file });
    } catch (x) {
      setErr(x instanceof ApiFailure ? x.message : 'Could not read the file.');
    } finally {
      setReading(false);
      if (input.current) input.current.value = ''; // the same file can be picked again
    }
  }

  return (
    <div className="space-y-2 text-right">
      <label className={`btn-ghost cursor-pointer py-1 ${reading || disabled ? 'opacity-50' : ''}`}>
        {reading ? 'Reading…' : 'Fill from Excel / CSV'}
        <input ref={input} type="file" accept=".xlsx,.csv" className="sr-only" onChange={read} disabled={reading || disabled} />
      </label>
      {err && <p className="text-sm text-red-700">{err}</p>}
      {choice && (
        <div className="rounded-lg border bg-white p-2 text-left text-sm">
          <p className="mb-1 font-medium">This file has {choice.leads.length}{choice.more ? '+' : ''} rows. Pick the lead to fill in:</p>
          {choice.more && <p className="mb-1 text-xs text-slate-500">Only the first {choice.leads.length} rows are shown.</p>}
          <ul className="max-h-60 divide-y overflow-auto">
            {choice.leads.map((l, i) => (
              <li key={i}>
                <button type="button" disabled={disabled} className="w-full px-2 py-1.5 text-left hover:bg-slate-50 disabled:opacity-50"
                  onClick={() => { onPick(l, choice.file); setChoice(null); }}>
                  {[l.fields.name, l.fields.company, l.fields.phone].filter(Boolean).join(' · ') || `Row ${i + 2}`}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
