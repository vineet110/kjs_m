'use client';
// Team attendance: who is in today (or any day), and missed-punch requests to approve.
import { useCallback, useEffect, useState } from 'react';
import { addDays, EmptyState, fmtDay, PageTitle, Pill, todayIST } from '@/components/portal/ui';
import { api, ApiFailure, type Regularization } from '@/lib/api';
import Loading from '@/components/ui/Loading';

type Row = { user_id: number; name: string; is_available: boolean; state: string; check_in: string | null; check_out: string | null; hours: number };

export default function TeamAttendance() {
  const [day, setDay] = useState(todayIST());
  const [rows, setRows] = useState<Row[] | null>(null);
  const [pending, setPending] = useState<Regularization[]>([]);
  const [err, setErr] = useState('');

  const load = useCallback(() => {
    api<Row[]>(`/attendance/team?day=${day}`).then(setRows).catch(() => setRows([]));
    api<Regularization[]>('/attendance/approvals').then(setPending);
  }, [day]);
  useEffect(() => {
    load();
  }, [load]);

  async function decide(id: number, approve: boolean) {
    setErr('');
    try {
      await api(`/attendance/approvals/${id}`, { method: 'POST', body: { approve } });
      load();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
    }
  }

  const counts = (rows ?? []).reduce<Record<string, number>>((acc, r) => ({ ...acc, [r.state]: (acc[r.state] ?? 0) + 1 }), {});

  return (
    <div className="space-y-6">
      <PageTitle title="Team attendance" sub="Times in IST.">
        <div className="flex items-center gap-2">
          <button className="btn-ghost py-1" onClick={() => setDay(addDays(day, -1))}>←</button>
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="input w-auto" />
          <button className="btn-ghost py-1" onClick={() => setDay(addDays(day, 1))}>→</button>
        </div>
      </PageTitle>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">Missed-punch requests ({pending.length})</h2>
        {err && <p className="text-sm text-red-700">{err}</p>}
        {pending.length === 0 && <EmptyState tone="done" title="Nothing waiting" text="Missed-punch requests from the team show here." />}
        {pending.map((r) => (
          <div key={r.id} className="card flex flex-wrap items-center gap-3 p-4 text-sm">
            <span className="font-semibold">{r.user_name}</span>
            <span>{fmtDay(r.day, true)} · {r.check_in}–{r.check_out ?? '?'}</span>
            <span className="text-slate-500">“{r.reason}”</span>
            <span className="ml-auto flex gap-2">
              <button onClick={() => decide(r.id, true)} className="btn-dark py-1">Approve</button>
              <button onClick={() => decide(r.id, false)} className="btn-ghost py-1">Reject</button>
            </span>
          </div>
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">{fmtDay(day, true)}</h2>
        <div className="flex flex-wrap gap-2 text-sm">
          {Object.entries(counts).map(([k, v]) => <span key={k} className="flex items-center gap-1"><Pill value={k} /> {v}</span>)}
        </div>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="p-3">Name</th><th className="p-3">Status</th><th className="p-3">In</th><th className="p-3">Out</th><th className="p-3">Hours</th><th className="p-3">Receiving tasks</th></tr>
            </thead>
            <tbody>
              {rows === null && <tr><td className="p-3" colSpan={6}><Loading /></td></tr>}
              {rows?.map((r) => (
                <tr key={r.user_id} className="border-t">
                  <td className="p-3 font-medium">{r.name}</td>
                  <td className="p-3"><Pill value={r.state} /></td>
                  <td className="p-3">{r.check_in ?? '—'}</td>
                  <td className="p-3">{r.check_out ?? '—'}</td>
                  <td className="p-3">{r.hours || '—'}</td>
                  <td className="p-3">{r.is_available ? 'On' : 'Off'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
