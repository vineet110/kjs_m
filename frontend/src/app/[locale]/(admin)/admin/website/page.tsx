'use client';
// Website: page text + SEO, offers ticker, partner applications. Changes show within a minute.
import { useCallback, useEffect, useState } from 'react';
import { useMe } from '@/components/portal/PortalShell';
import { fmtIST, Msg, PageTitle, Pill } from '@/components/portal/ui';
import { api, ApiFailure } from '@/lib/api';
import { partnerLabel } from '@/lib/partners';
import Loading from '@/components/ui/Loading';

type TextRow = { key: string; label: string; value: string; changed: boolean };
type OfferRow = { id: number; text: string; link: string; starts_at: string | null; ends_at: string | null; is_active: boolean; sort_order: number };
type Partner = { id: number; name: string; company: string; partner_type: string; country: string; email: string; phone: string; message: string; status: string; created_at: string };

const toLocal = (iso: string | null) => (iso ? new Date(iso).toLocaleString('sv-SE', { timeZone: 'Asia/Kolkata' }).slice(0, 16).replace(' ', 'T') : '');
const fromLocal = (v: string) => (v ? new Date(`${v}:00+05:30`).toISOString() : null);

export default function WebsiteAdmin() {
  const me = useMe();
  const canEdit = me.permissions.includes('content.edit');
  const [tab, setTab] = useState<'texts' | 'offers' | 'partners'>(canEdit ? 'texts' : 'partners');
  const tabs = [...(canEdit ? (['texts', 'offers'] as const) : []), ...(me.permissions.includes('leads.view_all') ? (['partners'] as const) : [])];
  return (
    <div className="space-y-6">
      <PageTitle title="Website" sub="Changes show on the website within a minute." />
      <div className="flex gap-2 text-sm">
        {tabs.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-full px-3 py-1 capitalize ${tab === t ? 'bg-forest text-white' : 'bg-white ring-1 ring-slate-200'}`}>
            {t === 'texts' ? 'Text & SEO' : t}
          </button>
        ))}
      </div>
      {tab === 'texts' && <Texts />}
      {tab === 'offers' && <Offers />}
      {tab === 'partners' && <Partners />}
    </div>
  );
}

function Texts() {
  const [rows, setRows] = useState<TextRow[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = useCallback(() => {
    api<TextRow[]>('/content/texts').then((r) => setRows(r.filter((x) => !x.key.startsWith('koko.'))));
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function save(key: string, value: string | null) {
    try {
      await api(`/content/texts/${key}`, { method: 'PUT', body: { value } });
      setMsg({ ok: true, text: value === null ? 'Back to the default text.' : 'Saved.' });
      load();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof ApiFailure ? e.message : 'Could not save.' });
    }
  }

  return (
    <div className="space-y-3">
      <Msg msg={msg} />
      {rows.map((r) => (
        <TextEditor key={r.key} row={r} onSave={save} />
      ))}
    </div>
  );
}

function TextEditor({ row, onSave }: { row: TextRow; onSave: (k: string, v: string | null) => void }) {
  const [v, setV] = useState(row.value);
  useEffect(() => setV(row.value), [row.value]);
  const isSeo = row.key.startsWith('seo.');
  const limit = row.key.endsWith('.title') ? 60 : row.key.endsWith('.description') ? 160 : 0;
  return (
    <div className="card space-y-2 p-4">
      <div className="flex items-center gap-2">
        <label className="text-sm font-semibold" htmlFor={row.key}>{row.label}</label>
        {isSeo && <Pill value="ok" label="Google" />}
        {row.changed && <Pill value="pending" label="edited" />}
        {limit > 0 && <span className={`ml-auto text-xs ${v.length > limit ? 'text-red-700' : 'text-slate-500'}`}>{v.length}/{limit} letters</span>}
      </div>
      <textarea id={row.key} value={v} onChange={(e) => setV(e.target.value)} rows={v.length > 120 ? 3 : 2} className="input" />
      <div className="flex gap-2">
        <button disabled={v === row.value} onClick={() => onSave(row.key, v)} className="btn-dark py-1">Save</button>
        {row.changed && <button onClick={() => onSave(row.key, null)} className="btn-ghost py-1">Back to default</button>}
      </div>
    </div>
  );
}

function Offers() {
  const [rows, setRows] = useState<OfferRow[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = useCallback(() => {
    api<OfferRow[]>('/content/offers').then(setRows);
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    try {
      await api('/content/offers', { method: 'POST', body: { text: f.text, link: f.link, starts_at: fromLocal(f.starts_at), ends_at: fromLocal(f.ends_at), sort_order: Number(f.sort_order || 0) } });
      setMsg({ ok: true, text: 'Offer added.' });
      form.reset();
      load();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save.' });
    }
  }

  async function toggle(o: OfferRow) {
    await api(`/content/offers/${o.id}`, { method: 'PATCH', body: { ...o, is_active: !o.is_active } });
    load();
  }

  async function remove(o: OfferRow) {
    if (!confirm(`Delete "${o.text}"?`)) return;
    await api(`/content/offers/${o.id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="space-y-4">
      <form onSubmit={add} className="card grid gap-3 p-4 md:grid-cols-6">
        <div className="md:col-span-3"><label className="label">Offer text</label><input name="text" required minLength={3} maxLength={200} className="input" placeholder="Free samples for new distributors this month" /></div>
        <div className="md:col-span-3"><label className="label">Link (optional)</label><input name="link" maxLength={255} className="input" placeholder="/private-label" /></div>
        <div className="md:col-span-2"><label className="label">Starts (IST, optional)</label><input type="datetime-local" name="starts_at" className="input" /></div>
        <div className="md:col-span-2"><label className="label">Ends (IST, optional)</label><input type="datetime-local" name="ends_at" className="input" /></div>
        <div><label className="label">Order</label><input type="number" name="sort_order" defaultValue={0} className="input" /></div>
        <div className="flex items-end"><button className="btn-dark w-full">Add</button></div>
        <div className="md:col-span-6"><Msg msg={msg} /></div>
      </form>
      <div className="card divide-y">
        {rows.length === 0 && <p className="p-4 text-sm text-slate-500">No offers yet. The ticker stays hidden until there is a live one.</p>}
        {rows.map((o) => (
          <div key={o.id} className="flex flex-wrap items-center gap-2 p-3 text-sm">
            <span className="font-medium">{o.text}</span>
            {o.link && <span className="text-xs text-slate-500">→ {o.link}</span>}
            <span className="text-xs text-slate-500">{o.starts_at ? `from ${toLocal(o.starts_at).replace('T', ' ')}` : ''} {o.ends_at ? `until ${toLocal(o.ends_at).replace('T', ' ')}` : ''}</span>
            <Pill value={o.is_active ? 'ok' : 'off'} label={o.is_active ? 'on' : 'off'} />
            <span className="ml-auto flex gap-3 text-xs">
              <button onClick={() => toggle(o)} className="underline">{o.is_active ? 'Switch off' : 'Switch on'}</button>
              <button onClick={() => remove(o)} className="text-red-700 underline">Delete</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Partners() {
  const [rows, setRows] = useState<Partner[] | null>(null);
  const load = useCallback(() => {
    api<Partner[]>('/content/partners').then(setRows).catch(() => setRows([]));
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  async function setStatus(p: Partner, status: string) {
    await api(`/content/partners/${p.id}/status`, { method: 'POST', body: { status } });
    load();
  }
  if (rows === null) return <Loading />;
  return (
    <div className="space-y-2">
      {rows.length === 0 && <p className="card p-4 text-sm text-slate-500">No partner applications yet.</p>}
      {rows.map((p) => (
        <div key={p.id} className="card space-y-1 p-4 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{p.name}</span>
            <span className="text-slate-500">{p.company && `${p.company} · `}{partnerLabel(p.partner_type)} · {p.country}</span>
            <Pill value={p.status === 'new' ? 'pending' : p.status} label={p.status} />
            <span className="ml-auto text-xs text-slate-400">{fmtIST(p.created_at)} IST</span>
          </div>
          <p><a href={`mailto:${p.email}`} className="underline">{p.email}</a>{p.phone && ` · ${p.phone}`}</p>
          {p.message && <p className="text-slate-600">“{p.message}”</p>}
          {p.status === 'new' && (
            <div className="flex gap-2 pt-1">
              <button onClick={() => setStatus(p, 'approved')} className="btn-dark py-1">Approve</button>
              <button onClick={() => setStatus(p, 'rejected')} className="btn-ghost py-1">Reject</button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
