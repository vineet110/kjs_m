'use client';
// Holiday calendar: used by attendance, order-board deadlines and auto-assign.
import { useCallback, useEffect, useState } from 'react';
import { useToast } from '@/components/portal/Toast';
import { fmtDay, Msg, PageTitle } from '@/components/portal/ui';
import { api, ApiFailure, type Holiday } from '@/lib/api';

export default function HolidaysPage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [rows, setRows] = useState<Holiday[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const toast = useToast();

  const load = useCallback(() => {
    api<Holiday[]>(`/admin/holidays?year=${year}`).then(setRows);
  }, [year]);
  useEffect(() => {
    load();
  }, [load]);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form));
    try {
      await api('/admin/holidays', { method: 'POST', body: f });
      setMsg(null);
      toast(`Added ${f.name} to the holidays`);
      form.reset();
      load();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save.' });
    }
  }

  async function remove(h: Holiday) {
    if (!confirm(`Remove ${h.name} (${fmtDay(h.day, true)})?`)) return;
    await api(`/admin/holidays/${h.id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="space-y-6">
      <PageTitle title="Holidays" sub="Working days are Monday to Saturday minus these dates.">
        <div className="flex items-center gap-2">
          <button className="btn-ghost py-1" onClick={() => setYear(year - 1)}>←</button>
          <span className="font-semibold">{year}</span>
          <button className="btn-ghost py-1" onClick={() => setYear(year + 1)}>→</button>
        </div>
      </PageTitle>
      <form onSubmit={add} className="card flex flex-wrap items-end gap-3 p-4">
        <div><label className="label">Date</label><input type="date" name="day" required className="input" /></div>
        <div className="min-w-[14rem] flex-1"><label className="label">Name</label><input name="name" required minLength={2} maxLength={120} className="input" placeholder="Diwali" /></div>
        <button className="btn-dark">Add holiday</button>
        <div className="w-full"><Msg msg={msg} /></div>
      </form>
      <div className="card divide-y">
        {rows.length === 0 && <p className="p-4 text-sm text-slate-500">No holidays for {year} yet.</p>}
        {rows.map((h) => (
          <div key={h.id} className="flex items-center justify-between p-3 text-sm">
            <span><span className="font-medium">{h.name}</span> <span className="text-slate-500">· {fmtDay(h.day, true)}</span></span>
            <button onClick={() => remove(h)} className="text-xs text-red-700 underline">Remove</button>
          </div>
        ))}
      </div>
    </div>
  );
}
