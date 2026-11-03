'use client';
// My batches: buyer records given to me automatically. Work through each one and mark it done or skipped.
import { useCallback, useEffect, useState } from 'react';
import { fmtDay, PageTitle, Pill } from '@/components/portal/ui';
import { api, ApiFailure, type BatchInfo, type BuyerRecord } from '@/lib/api';
import Loading from '@/components/ui/Loading';

export default function MyBatches() {
  const [batches, setBatches] = useState<BatchInfo[] | null>(null);
  const load = useCallback(() => {
    api<BatchInfo[]>('/assign/my-batches').then(setBatches).catch(() => setBatches([]));
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  if (batches === null) return <Loading />;
  const open = batches.find((b) => b.status === 'open');
  const past = batches.filter((b) => b.status !== 'open');

  return (
    <div className="space-y-6">
      <PageTitle title="My batches" sub="Records come to you automatically while you are checked in and receiving tasks." />
      {!open && <p className="card p-6 text-sm text-slate-500">No open batch. A new one arrives when records are waiting in your categories.</p>}
      {open && (
        <section className="space-y-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold">Batch of {fmtDay(open.day)}</h2>
            <span className="text-sm text-slate-500">{open.done} of {open.size} done</span>
            <div className="h-2 flex-1 overflow-hidden rounded bg-slate-100"><div className="h-2 bg-gold" style={{ width: `${(open.done / open.size) * 100}%` }} /></div>
          </div>
          {open.records.map((r) => <RecordCard key={r.id} r={r} onDone={load} />)}
        </section>
      )}
      {past.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-bold">Finished</h2>
          <div className="card divide-y text-sm">
            {past.map((b) => <div key={b.id} className="flex justify-between p-3"><span>{fmtDay(b.day, true)}</span><span className="text-slate-500">{b.done} of {b.size} records</span></div>)}
          </div>
        </section>
      )}
    </div>
  );
}

function RecordCard({ r, onDone }: { r: BuyerRecord; onDone: () => void }) {
  const [outcome, setOutcome] = useState(r.outcome);
  const [err, setErr] = useState('');
  const finished = r.status === 'done' || r.status === 'skipped';

  async function set(status: 'done' | 'skipped' | 'assigned') {
    setErr('');
    try {
      await api(`/assign/records/${r.id}`, { method: 'PATCH', body: { status, outcome } });
      onDone();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
    }
  }

  return (
    <div className={`card space-y-2 p-4 ${finished ? 'opacity-70' : ''}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{r.company}</span>
        {r.country && <span className="text-sm text-slate-500">· {r.country}</span>}
        <span className="text-xs text-slate-500">{r.category}</span>
        <span className="ml-auto"><Pill value={finished ? (r.status === 'done' ? 'done' : 'off') : 'todo'} label={r.status === 'assigned' ? 'to do' : r.status} /></span>
      </div>
      <div className="flex flex-wrap gap-x-4 text-sm">
        {r.contact_name && <span>{r.contact_name}</span>}
        {r.email && <a href={`mailto:${r.email}`} className="underline">{r.email}</a>}
        {r.phone && <a href={`tel:${r.phone}`} className="underline">{r.phone}</a>}
        {r.website && <a href={r.website.startsWith('http') ? r.website : `https://${r.website}`} target="_blank" rel="noreferrer" className="underline">{r.website}</a>}
      </div>
      {r.notes && <p className="text-sm text-slate-600">{r.notes}</p>}
      <div className="flex flex-wrap gap-2">
        <input value={outcome} onChange={(e) => setOutcome(e.target.value)} maxLength={300} placeholder="Outcome: e.g. emailed catalogue, wants samples" className="input min-w-[14rem] flex-1" />
        {!finished ? (
          <>
            <button onClick={() => set('done')} className="btn-dark">Done</button>
            <button onClick={() => set('skipped')} className="btn-ghost">Skip</button>
          </>
        ) : <button onClick={() => set('assigned')} className="btn-ghost">Undo</button>}
      </div>
      {err && <p className="text-sm text-red-700">{err}</p>}
    </div>
  );
}
