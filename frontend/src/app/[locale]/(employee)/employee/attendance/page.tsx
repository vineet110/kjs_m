'use client';
// Attendance: today, week view with hours, regularization requests, holiday list.
import { useCallback, useEffect, useState } from 'react';
import TodayCard from '@/components/portal/TodayCard';
import { addDays, fmtDay, Msg, PageTitle, Pill, todayIST } from '@/components/portal/ui';
import { api, ApiFailure, type Holiday, type Regularization, type Week } from '@/lib/api';

export default function AttendancePage() {
  const [start, setStart] = useState(todayIST());
  const [week, setWeek] = useState<Week | null>(null);
  const [regs, setRegs] = useState<Regularization[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    api<Week>(`/attendance/week?start=${start}`).then(setWeek);
    api<Regularization[]>('/attendance/regularizations').then(setRegs);
  }, [start]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    api<Holiday[]>('/attendance/holidays').then(setHolidays);
  }, []);

  async function regularize(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    try {
      await api('/attendance/regularizations', {
        method: 'POST',
        body: { day: f.day, check_in: f.check_in, check_out: f.check_out || null, reason: f.reason },
      });
      setMsg({ ok: true, text: 'Request sent. You will see the result below.' });
      form.reset();
      load();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not send.' });
    }
  }

  return (
    <div className="space-y-6">
      <PageTitle title="Attendance" sub="Times shown in IST. Working days are Monday to Saturday, minus holidays." />
      <TodayCard onChange={load} />

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold">Week of {week ? fmtDay(week.week_start, true) : '…'}</h2>
          <div className="flex gap-2">
            <button className="btn-ghost py-1" onClick={() => setStart(addDays(week?.week_start ?? start, -7))}>← Previous</button>
            <button className="btn-ghost py-1" onClick={() => setStart(todayIST())}>This week</button>
            <button className="btn-ghost py-1" onClick={() => setStart(addDays(week?.week_start ?? start, 7))}>Next →</button>
          </div>
        </div>
        {week && (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-6">
              {(['present', 'late', 'absent', 'leave', 'holiday'] as const).map((k) => (
                <div key={k} className="card p-3">
                  <p className="text-xs font-semibold uppercase text-slate-500">{k}</p>
                  <p className="text-2xl font-bold">{week.summary[k] ?? 0}</p>
                </div>
              ))}
              <div className="card p-3">
                <p className="text-xs font-semibold uppercase text-slate-500">Hours</p>
                <p className="text-2xl font-bold">{week.total_hours}</p>
              </div>
            </div>
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr><th className="p-3">Day</th><th className="p-3">Status</th><th className="p-3">In</th><th className="p-3">Out</th><th className="p-3">Hours</th><th className="p-3">Timeline</th></tr>
                </thead>
                <tbody>
                  {week.days.map((d) => (
                    <tr key={d.day} className="border-t">
                      <td className="p-3 font-medium">{fmtDay(d.day)}</td>
                      <td className="p-3"><Pill value={d.state} /></td>
                      <td className="p-3">{d.check_in ?? '—'}</td>
                      <td className="p-3">{d.check_out ?? '—'}</td>
                      <td className="p-3">{d.hours || '—'}</td>
                      <td className="w-1/3 p-3"><Timeline checkIn={d.check_in} checkOut={d.check_out} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-3">
          <h2 className="text-lg font-bold">Missed a punch?</h2>
          <form onSubmit={regularize} className="card grid gap-3 p-4 sm:grid-cols-3">
            <div><label className="label">Day</label><input type="date" name="day" required max={todayIST()} className="input" /></div>
            <div><label className="label">Check in</label><input type="time" name="check_in" required className="input" /></div>
            <div><label className="label">Check out</label><input type="time" name="check_out" className="input" /></div>
            <div className="sm:col-span-3"><label className="label">Reason</label><input name="reason" required minLength={3} maxLength={500} className="input" placeholder="Forgot to check in, was at the warehouse" /></div>
            <div className="sm:col-span-3"><Msg msg={msg} /></div>
            <div><button className="btn-dark">Send request</button></div>
          </form>
          <div className="card divide-y">
            {regs.length === 0 && <p className="p-4 text-sm text-slate-500">No requests yet.</p>}
            {regs.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center gap-2 p-3 text-sm">
                <span className="font-medium">{fmtDay(r.day)}</span>
                <span>{r.check_in}–{r.check_out ?? '?'}</span>
                <span className="text-slate-500">“{r.reason}”</span>
                <span className="ml-auto"><Pill value={r.status} /></span>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-bold">Holidays this year</h2>
          <div className="card divide-y">
            {holidays.length === 0 && <p className="p-4 text-sm text-slate-500">No holidays added yet.</p>}
            {holidays.map((h) => (
              <div key={h.id} className="flex justify-between p-3 text-sm">
                <span>{h.name}</span><span className="text-slate-500">{fmtDay(h.day, true)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

/** A thin bar for the day from 07:00 to 21:00 showing when the person was in. */
function Timeline({ checkIn, checkOut }: { checkIn: string | null; checkOut: string | null }) {
  if (!checkIn) return <div className="h-2 rounded bg-slate-100" />;
  const toPct = (t: string) => {
    const [h, m] = t.split(':').map(Number);
    return Math.min(100, Math.max(0, ((h + m / 60 - 7) / 14) * 100));
  };
  const left = toPct(checkIn);
  const right = checkOut ? toPct(checkOut) : left + 2;
  return (
    <div className="relative h-2 rounded bg-slate-100" title={`${checkIn}–${checkOut ?? 'now'}`}>
      <div className="absolute h-2 rounded bg-forest" style={{ left: `${left}%`, width: `${Math.max(2, right - left)}%` }} />
    </div>
  );
}
