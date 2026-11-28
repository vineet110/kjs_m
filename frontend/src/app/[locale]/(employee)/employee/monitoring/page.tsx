'use client';
// My activity: my own day as the laptop-monitoring server measured it (worked, active, idle, top apps and sites).
// Everyone may see their own day; nothing here is anyone else's.
import { useCallback, useEffect, useState } from 'react';
import { EmptyState, PageTitle, todayIST } from '@/components/portal/ui';
import { useMe } from '@/components/portal/PortalShell';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';
import { api, ApiFailure } from '@/lib/api';
import { canSee } from '@/lib/modules';
import { minutes, type DayReport } from '@/lib/monitoring';

export default function MyActivityPage() {
  const me = useMe();
  const on = canSee(me, 'monitoring');
  const [day, setDay] = useState(todayIST());
  const [r, setR] = useState<DayReport | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [none, setNone] = useState(false);
  const load = useCallback(() => {
    setErr(null); setNone(false); setR(null);
    api<DayReport>(`/monitoring/me/today?date=${day}`).then(setR).catch((e) => {
      if (e instanceof ApiFailure && e.status === 404) setNone(true); // no laptop enrolled yet
      else setErr(e);
    });
  }, [day]);
  useEffect(() => { if (on) load(); }, [on, load]);

  if (!on) return <EmptyState title="Laptop monitoring is not switched on yet" />;
  return (
    <div className="space-y-6">
      <PageTitle title="My activity" sub="Your working time as your laptop recorded it. Only you and your manager see this.">
        <input type="date" className="input" value={day} max={todayIST()} onChange={(e) => e.target.value && setDay(e.target.value)} aria-label="Day" />
      </PageTitle>
      {err ? <LoadError error={err} onRetry={load} /> : none ? (
        <EmptyState title="No laptop data yet" text="Your activity shows here once your laptop is set up for monitoring." />
      ) : !r ? <Loading /> : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Figure label="Worked" value={minutes(r.worked_min)} />
            <Figure label="Active" value={minutes(r.active_min)} />
            <Figure label="Idle" value={minutes(r.idle_min)} />
            <Figure label="Productive" value={r.productive_pct === null ? '-' : `${Math.round(r.productive_pct)}%`} />
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Top title="Top apps" rows={r.top_apps ?? []} />
            <Top title="Top websites" rows={r.top_sites ?? []} />
          </div>
        </>
      )}
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
    </div>
  );
}

function Top({ title, rows }: { title: string; rows: { name: string; minutes: number }[] }) {
  return (
    <section className="card p-4 text-sm">
      <h2 className="mb-2 font-semibold">{title}</h2>
      {rows.length === 0 ? <p className="text-slate-500">Nothing recorded.</p> : (
        <ul className="space-y-1">
          {rows.slice(0, 10).map((x) => (
            <li key={x.name} className="flex justify-between gap-3"><span className="truncate">{x.name}</span><span className="text-slate-500">{minutes(x.minutes)}</span></li>
          ))}
        </ul>
      )}
    </section>
  );
}
