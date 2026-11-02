'use client';
// Leads list used by "My day" (own + unassigned) and the admin "All leads" page (everyone's).
// Each card shows the SLA timer; logging a call/email or marking "contacted" stops the respond timer.
import { useCallback, useEffect, useState } from 'react';
import { api, ApiFailure, type Colleague, type Lead, type LeadNote } from '@/lib/api';
import { fmtIST, Pill } from './ui';
import Loading from '@/components/ui/Loading';

const SOURCE_LABEL: Record<string, string> = { enquiry_form: 'Enquiry', price_sheet: 'Price sheet', koko: 'Koko chat', gated: 'Gated form' };
const OUTCOMES = ['quote_sent', 'sample_sent', 'order_won', 'not_interested', 'no_reply', 'spam'];

export default function LeadsTable({ admin = false }: { admin?: boolean }) {
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [status, setStatus] = useState('');
  const [sla, setSla] = useState('');
  const [owner, setOwner] = useState('');
  const [staff, setStaff] = useState<Colleague[]>([]);
  const [open, setOpen] = useState<number | null>(null);

  const load = useCallback(() => {
    const qs = new URLSearchParams();
    if (status) qs.set('status', status);
    if (admin && sla) qs.set('sla', sla);
    if (admin && owner) qs.set('owner', owner);
    api<Lead[]>(`${admin ? '/admin/leads' : '/employee/leads'}?${qs}`).then(setLeads).catch(() => setLeads([]));
  }, [status, sla, owner, admin]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    api<Colleague[]>('/employee/colleagues').then(setStaff);
  }, []);
  // Timers move: refresh every minute.
  useEffect(() => {
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {['', 'new', 'contacted', 'closed'].map((s) => (
          <button key={s} onClick={() => setStatus(s)} className={`rounded-full px-3 py-1 ${status === s ? 'bg-forest text-white' : 'bg-white text-slate-600 ring-1 ring-slate-200'}`}>
            {s || 'All'}
          </button>
        ))}
        {admin && (
          <>
            <select value={sla} onChange={(e) => setSla(e.target.value)} className="input w-auto py-1">
              <option value="">Any SLA</option><option value="overdue">Overdue</option><option value="due_soon">Due soon</option><option value="ok">On time</option>
            </select>
            <select value={owner} onChange={(e) => setOwner(e.target.value)} className="input w-auto py-1">
              <option value="">Any owner</option>
              {staff.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </>
        )}
      </div>
      {leads === null && <Loading />}
      {leads?.length === 0 && <div className="card p-6 text-sm text-slate-500">No leads here. New ones appear as soon as a visitor sends an enquiry or talks to Koko.</div>}
      {leads?.map((l) => (
        <div key={l.id} className={`card space-y-2 p-4 ${l.sla_state === 'overdue' ? 'border-red-300' : ''}`}>
          <div className="flex flex-wrap items-center gap-2">
            <Pill value={l.status} />
            <Pill value={l.sla_state === 'done' ? 'closed' : l.sla_state} label={l.sla_label} />
            <span className="font-semibold">{l.name}</span>
            {l.company && <span className="text-sm text-slate-500">· {l.company}</span>}
            {l.country && <span className="text-sm text-slate-500">· {l.country}</span>}
            <span className="ml-auto text-xs text-slate-400">
              {SOURCE_LABEL[l.source] ?? l.source} · {fmtIST(l.created_at)} IST · {l.owner_name ? `Owner: ${l.owner_name}` : 'Unassigned'}
            </span>
          </div>
          <div className="grid gap-1 text-sm text-slate-700 sm:grid-cols-4">
            {l.email && <a href={`mailto:${l.email}`} className="truncate underline">{l.email}</a>}
            {l.phone && <a href={`tel:${l.phone}`} className="underline">{l.phone}</a>}
            {(l.product_name || l.category_name) && <span>Interested in: {l.product_name || l.category_name}</span>}
            {l.quantity && <span>Qty: {l.quantity}</span>}
          </div>
          {l.message && <p className="text-sm text-slate-600">“{l.message}”</p>}
          {l.chat_summary && (
            <div className="rounded-lg bg-slate-50 p-3 text-sm">
              <p className="mb-1 text-xs font-semibold uppercase text-slate-500">Koko chat summary</p>
              <p className="whitespace-pre-wrap">{l.chat_summary}</p>
            </div>
          )}
          {l.outcome && <p className="text-xs text-slate-500">Outcome: {l.outcome.replace(/_/g, ' ')}</p>}
          <button onClick={() => setOpen(open === l.id ? null : l.id)} className="text-xs font-semibold underline">
            {open === l.id ? 'Hide actions' : `Work on it${l.note_count ? ` · ${l.note_count} notes` : ''}`}
          </button>
          {open === l.id && <LeadActions lead={l} staff={staff} admin={admin} onDone={load} />}
        </div>
      ))}
    </div>
  );
}

function LeadActions({ lead, staff, admin, onDone }: { lead: Lead; staff: Colleague[]; admin: boolean; onDone: () => void }) {
  const [notes, setNotes] = useState<LeadNote[]>([]);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const loadNotes = useCallback(() => {
    api<LeadNote[]>(`/employee/leads/${lead.id}/notes`).then(setNotes).catch(() => setNotes([]));
  }, [lead.id]);
  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setErr('');
    try {
      await fn();
      loadNotes();
      onDone();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
    } finally {
      setBusy(false);
    }
  }

  async function addNote(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form));
    await run(() => api(`/employee/leads/${lead.id}/notes`, { method: 'POST', body: f }));
    form.reset();
  }

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 p-3">
      {notes.length > 0 && (
        <ul className="space-y-1 text-sm">
          {notes.map((n) => (
            <li key={n.id}><span className="text-xs text-slate-400">{fmtIST(n.created_at)} · {n.user_name} · {n.kind}</span><br />{n.text}</li>
          ))}
        </ul>
      )}
      <form onSubmit={addNote} className="flex flex-wrap gap-2">
        <select name="kind" className="input w-auto"><option value="call">Call</option><option value="email">Email</option><option value="note">Note</option></select>
        <input name="text" required maxLength={2000} placeholder="What happened? e.g. Called, wants samples of 3-in-1" className="input min-w-[12rem] flex-1" />
        <button disabled={busy} className="btn-dark">Log</button>
      </form>
      <div className="flex flex-wrap items-center gap-2">
        {lead.status === 'new' && <button disabled={busy} onClick={() => run(() => api(`/employee/leads/${lead.id}`, { method: 'PATCH', body: { status: 'contacted' } }))} className="btn-ghost py-1 text-xs">Mark contacted</button>}
        {lead.status !== 'closed' && (
          <select
            disabled={busy}
            defaultValue=""
            onChange={(e) => e.target.value && run(() => api(`/employee/leads/${lead.id}`, { method: 'PATCH', body: { status: 'closed', outcome: e.target.value } }))}
            className="input w-auto py-1 text-xs"
          >
            <option value="">Close with outcome…</option>
            {OUTCOMES.map((o) => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
          </select>
        )}
        {lead.status === 'closed' && <button disabled={busy} onClick={() => run(() => api(`/employee/leads/${lead.id}`, { method: 'PATCH', body: { status: 'contacted' } }))} className="btn-ghost py-1 text-xs">Reopen</button>}
        <select
          disabled={busy}
          defaultValue=""
          onChange={(e) => e.target.value && run(() => api(admin ? `/admin/leads/${lead.id}/assign` : `/employee/leads/${lead.id}/handover`, { method: 'POST', body: { user_id: Number(e.target.value) } }))}
          className="input w-auto py-1 text-xs"
        >
          <option value="">{admin ? 'Assign to…' : 'Hand over to…'}</option>
          {staff.filter((c) => c.id !== lead.assigned_to).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      {err && <p className="text-sm text-red-700">{err}</p>}
    </div>
  );
}
