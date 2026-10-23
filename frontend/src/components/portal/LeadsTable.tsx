'use client';
import { useCallback, useEffect, useState } from 'react';
import { api, type Lead } from '@/lib/api';

const SOURCE_LABEL: Record<string, string> = { enquiry_form: 'Enquiry', price_sheet: 'Price sheet', koko: 'Koko chat' };
const STATUS_STYLE: Record<string, string> = {
  new: 'bg-amber-100 text-amber-800',
  contacted: 'bg-sky-100 text-sky-800',
  closed: 'bg-slate-200 text-slate-700',
};

export default function LeadsTable() {
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [filter, setFilter] = useState<string>('');

  const load = useCallback(() => {
    api<Lead[]>(`/employee/leads${filter ? `?status=${filter}` : ''}`).then(setLeads).catch(() => setLeads([]));
  }, [filter]);
  useEffect(() => {
    load();
  }, [load]);

  async function setStatus(id: number, status: Lead['status']) {
    await api(`/employee/leads/${id}`, { method: 'PATCH', body: { status } });
    load();
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2 text-sm">
        {['', 'new', 'contacted', 'closed'].map((s) => (
          <button key={s} onClick={() => setFilter(s)} className={`rounded-full px-3 py-1 ${filter === s ? 'bg-forest text-white' : 'bg-white text-slate-600 ring-1 ring-slate-200'}`}>
            {s || 'All'}
          </button>
        ))}
      </div>
      {leads === null && <p className="text-sm text-slate-500">Loading…</p>}
      {leads?.length === 0 && <div className="card p-6 text-sm text-slate-500">No leads yet. They appear here as soon as a visitor sends an enquiry or talks to Koko.</div>}
      {leads?.map((l) => (
        <div key={l.id} className="card space-y-2 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[l.status]}`}>{l.status}</span>
            <span className="font-semibold">{l.name}</span>
            {l.company && <span className="text-sm text-slate-500">· {l.company}</span>}
            {l.country && <span className="text-sm text-slate-500">· {l.country}</span>}
            <span className="ml-auto text-xs text-slate-400">
              {SOURCE_LABEL[l.source] ?? l.source} · {new Date(l.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
            </span>
          </div>
          <div className="grid gap-1 text-sm text-slate-700 sm:grid-cols-4">
            {l.email && <a href={`mailto:${l.email}`} className="truncate underline">{l.email}</a>}
            {l.phone && <span>{l.phone}</span>}
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
          <div className="flex gap-2">
            {l.status !== 'contacted' && <button onClick={() => setStatus(l.id, 'contacted')} className="btn-ghost py-1 text-xs">Mark contacted</button>}
            {l.status !== 'closed' && <button onClick={() => setStatus(l.id, 'closed')} className="btn-ghost py-1 text-xs">Close</button>}
          </div>
        </div>
      ))}
    </div>
  );
}
