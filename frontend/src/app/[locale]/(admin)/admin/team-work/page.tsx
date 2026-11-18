'use client';
// Team work (monitor.view): who is in today and what each person did. Read-only; reloads itself every
// `refresh_seconds` (config/monitoring.ini). Search, sort by any column, and a short or full set of columns.
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { addDays, EmptyState, fmtDay, PageTitle, Pill, todayIST } from '@/components/portal/ui';
import StatTile from '@/components/portal/StatTile';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';
import { api, type TeamWork, type TeamWorkRow } from '@/lib/api';

type Key = keyof TeamWorkRow;
type Col = { key: Key; label: string; all?: boolean }; // all = only in "All columns"
const COLS: Col[] = [
  { key: 'name', label: 'Employee' }, { key: 'state', label: 'Status' }, { key: 'check_in', label: 'In' },
  { key: 'check_out', label: 'Out', all: true }, { key: 'hours', label: 'Hours' }, { key: 'calls', label: 'Calls' },
  { key: 'emails', label: 'Emails', all: true }, { key: 'notes', label: 'Notes', all: true },
  { key: 'outcomes', label: 'Outcomes', all: true }, { key: 'tasks_done', label: 'Tasks done' }, { key: 'chat', label: 'Chat', all: true },
  { key: 'break_minutes', label: 'Break (min)' }, { key: 'idle_minutes', label: 'Idle now (min)', all: true },
  { key: 'sharing', label: 'Screen' }, { key: 'device', label: 'Device', all: true },
  { key: 'site_minutes', label: 'Sites (min)', all: true }, { key: 'extension', label: 'Extension' },
];
const SHARING: Record<string, string> = { started: 'Shared', stopped: 'Stopped', refused: 'Refused' };
const ROSTER_LABEL: Record<string, string> = { upcoming: 'Yet to check in', leave: 'On leave' };

export default function TeamWorkPage() {
  const [day, setDay] = useState(todayIST());
  const [data, setData] = useState<TeamWork | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [q, setQ] = useState('');
  const [all, setAll] = useState(false);
  const [sort, setSort] = useState<{ key: Key; up: boolean }>({ key: 'name', up: true });

  const load = useCallback(() => {
    setErr(null);
    api<TeamWork>(`/work/team?day=${day}`).then(setData).catch(setErr);
  }, [day]);
  useEffect(() => { setData(null); load(); }, [load]);
  // Reload quietly while the page is open (only for today: past days don't change)
  const every = data?.refresh_seconds ?? 30;
  useEffect(() => {
    if (day !== todayIST()) return;
    const t = setInterval(() => { if (document.visibilityState === 'visible') load(); }, every * 1000);
    return () => clearInterval(t);
  }, [day, every, load]);

  const rows = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const found = (data?.rows ?? []).filter((r) => words.every((w) => r.name.toLowerCase().includes(w)));
    const v = (r: TeamWorkRow) => r[sort.key] ?? '';
    return [...found].sort((a, b) => (v(a) < v(b) ? -1 : v(a) > v(b) ? 1 : 0) * (sort.up ? 1 : -1));
  }, [data, q, sort]);
  const cols = COLS.filter((c) => all || !c.all);
  const s = data?.summary;

  return (
    <div className="space-y-6">
      <PageTitle title="Team work" sub={`${fmtDay(day, true)} · ${day === todayIST() ? `updates every ${every} seconds` : 'past day'}`}>
        <div className="flex items-center gap-1">
          <button className="btn-ghost py-1" aria-label="Previous day" onClick={() => setDay(addDays(day, -1))}>←</button>
          <input type="date" value={day} max={todayIST()} onChange={(e) => e.target.value && setDay(e.target.value)} className="input w-auto py-1 text-xs" />
          <button className="btn-ghost py-1" aria-label="Next day" disabled={day >= todayIST()} onClick={() => setDay(addDays(day, 1))}>→</button>
        </div>
      </PageTitle>

      {err != null && <LoadError error={err} onRetry={load} />}
      {s && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Checked in now" value={s.checked_in_now} icon="check" tone="green" />
          <StatTile label="Checked out" value={s.checked_out} icon="clock" tone="slate" />
          <StatTile label="Not in" value={s.not_in} icon="user" tone="gold" />
          <StatTile label="On break" value={s.on_break} icon="clock" tone="blue" />
        </div>
      )}

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div role="group" aria-label="Columns" className="flex overflow-hidden rounded-lg border border-slate-300 text-xs font-semibold">
            <button aria-pressed={!all} onClick={() => setAll(false)} className={`px-3 py-1.5 ${!all ? 'bg-ink text-white' : 'bg-white'}`}>Summary</button>
            <button aria-pressed={all} onClick={() => setAll(true)} className={`px-3 py-1.5 ${all ? 'bg-ink text-white' : 'bg-white'}`}>All columns</button>
          </div>
          <label className="block w-full max-w-xs">
            <span className="sr-only">Search by name</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name" className="input rounded-full" />
          </label>
        </div>

        {!data && err == null && <Loading />}
        {data && rows.length === 0 && <EmptyState title={q ? 'Nobody matches your search' : 'No active staff'} />}
        {data && rows.length > 0 && (
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-sky-50/70 text-xs font-semibold text-slate-600">
                <tr>
                  {cols.map((c) => (
                    <th key={c.key} className="px-4 py-3" aria-sort={sort.key === c.key ? (sort.up ? 'ascending' : 'descending') : 'none'}>
                      <button className="font-semibold hover:text-ink"
                        onClick={() => setSort((o) => ({ key: c.key, up: o.key === c.key ? !o.up : c.key === 'name' }))}>
                        {c.label} {sort.key === c.key ? (sort.up ? '↑' : '↓') : ''}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((r) => (
                  <tr key={r.user_id}>
                    {cols.map((c) => (
                      <td key={c.key} className="px-4 py-3">
                        {c.key === 'name' ? (
                          <Link href={`/admin/team-work/${r.user_id}`} className="font-medium text-sky-700 hover:underline">{r.name}</Link>
                        ) : c.key === 'state' ? (
                          <Pill value={r.on_break ? 'leave' : r.idle_minutes ? 'pending' : r.state}
                            label={r.on_break ? 'On break' : r.idle_minutes ? `Idle ${r.idle_minutes}m` : r.check_in && !r.check_out && day === todayIST() ? 'Checked in' : ROSTER_LABEL[r.state]} />
                        ) : c.key === 'sharing' ? (
                          r.sharing ? <Pill value={r.sharing === 'started' ? 'ok' : 'overdue'} label={SHARING[r.sharing]} /> : '–'
                        ) : c.key === 'extension' ? (
                          r.extension === 'connected' ? <Pill value="ok" label="Connected" /> : <span className="text-xs text-slate-500">Not connected</span>
                        ) : c.key === 'idle_minutes' ? (
                          r.extension === 'not_connected' ? <span className="text-xs text-slate-500">No extension</span> : (r.idle_minutes || '–')
                        ) : (
                          String(r[c.key] ?? '–')
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
