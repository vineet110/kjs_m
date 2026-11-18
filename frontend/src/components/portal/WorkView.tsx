'use client';
// One person's work, read-only: tabs Overview, Timeline, Tasks, Attendance. Used by Team work (admin, any
// person: base = "/work/12") and My work (own data: base = "/work/me"). The server decides whose data it is;
// this screen only shows it. Range limit and page size come from config/monitoring.ini (the server checks).
import { useCallback, useEffect, useState } from 'react';
import { addDays, EmptyState, fmtDay, Pill, todayIST } from './ui';
import StatTile from './StatTile';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';
import {
  api, type MonthView, type Task, type Timeline, type TimelineItem, type TimelineKind, type WorkOverview,
} from '@/lib/api';

type Tab = 'overview' | 'timeline' | 'tasks' | 'attendance';
const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' }, { id: 'timeline', label: 'Timeline' },
  { id: 'tasks', label: 'Tasks' }, { id: 'attendance', label: 'Attendance' },
];

export default function WorkView({ base, onPerson }: { base: string; onPerson?: (o: WorkOverview) => void }) {
  const [tab, setTab] = useState<Tab>('overview');
  const [from, setFrom] = useState(todayIST());
  const [to, setTo] = useState(todayIST());
  const range = `from=${from}&to=${to}`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div role="tablist" aria-label="Work sections" className="flex gap-1 overflow-x-auto overflow-y-hidden border-b">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
              className={`-mb-px shrink-0 border-b-2 px-4 py-2 text-sm font-semibold ${tab === t.id ? 'border-gold text-ink' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
              {t.label}
            </button>
          ))}
        </div>
        {tab !== 'attendance' && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <button className="btn-ghost py-1" onClick={() => { setFrom(todayIST()); setTo(todayIST()); }}>Today</button>
            <button className="btn-ghost py-1" onClick={() => { setFrom(addDays(todayIST(), -6)); setTo(todayIST()); }}>Last 7 days</button>
            <label className="flex items-center gap-1">From
              <input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} className="input w-auto py-1 text-xs" />
            </label>
            <label className="flex items-center gap-1">To
              <input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} className="input w-auto py-1 text-xs" />
            </label>
          </div>
        )}
      </div>

      {tab === 'overview' && <Overview url={`${base}/overview?${range}`} onPerson={onPerson} />}
      {tab === 'timeline' && <WorkTimeline url={`${base}/timeline?${range}`} />}
      {tab === 'tasks' && <Tasks url={`${base}/tasks?${range}`} />}
      {tab === 'attendance' && <Attendance base={base} />}
    </div>
  );
}

/** Loads one URL; a failure shows the error with "Try again", never an empty screen that looks like "nothing". */
function useLoad<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const load = useCallback(() => {
    setErr(null);
    setData(null);
    api<T>(url).then(setData).catch(setErr);
  }, [url]);
  useEffect(load, [load]);
  return { data, err, load };
}

function Overview({ url, onPerson }: { url: string; onPerson?: (o: WorkOverview) => void }) {
  const { data, err, load } = useLoad<WorkOverview>(url);
  useEffect(() => { if (data && onPerson) onPerson(data); }, [data, onPerson]);
  if (err) return <LoadError error={err} onRetry={load} />;
  if (!data) return <Loading />;
  const t = data.totals;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <StatTile label="Calls" value={t.calls} icon="phone" tone="blue" />
        <StatTile label="Emails" value={t.emails} icon="mail" tone="blue" />
        <StatTile label="Notes" value={t.notes} icon="note" tone="slate" />
        <StatTile label="Lead outcomes" value={t.outcomes} icon="check" tone="green" />
        <StatTile label="Tasks done" value={t.tasks_done} icon="tasks" tone="green" />
        <StatTile label="Chat messages" value={t.chat} icon="chat" tone="violet" />
        <StatTile label="Days present" value={t.days_present} icon="calendar" tone="gold" />
        <StatTile label="Hours worked" value={Math.round(t.hours)} icon="clock" tone="gold" hint={`${t.hours} h exactly`} />
      </div>
    </div>
  );
}

const KIND_LABEL: Record<TimelineKind, string> = {
  call: 'Calls', email: 'Emails', note: 'Notes', outcome: 'Lead outcomes', task: 'Tasks', chat: 'Chat', attendance: 'Check-in / out',
};
const KIND_COLOUR: Record<TimelineKind, string> = {
  call: 'text-sky-800', email: 'text-sky-800', note: 'text-slate-800', outcome: 'text-emerald-800',
  task: 'text-emerald-800', chat: 'text-violet-800', attendance: 'text-amber-800',
};

export function WorkTimeline({ url }: { url: string }) {
  const [kinds, setKinds] = useState<TimelineKind[]>([]); // none ticked = all
  const [items, setItems] = useState<TimelineItem[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [more, setMore] = useState(false);
  const full = `${url}${kinds.length ? `&kinds=${kinds.join(',')}` : ''}`;

  const load = useCallback(() => {
    setErr(null);
    setItems(null);
    api<Timeline>(full).then((t) => { setItems(t.items); setNext(t.next_before); }).catch(setErr);
  }, [full]);
  useEffect(load, [load]);

  async function loadMore() {
    if (!next) return;
    setMore(true);
    try {
      const t = await api<Timeline>(`${full}&before=${encodeURIComponent(next)}`);
      setItems((old) => [...(old ?? []), ...t.items]);
      setNext(t.next_before);
    } catch (e) {
      setErr(e);
    } finally {
      setMore(false);
    }
  }

  const toggle = (k: TimelineKind) => setKinds((ks) => (ks.includes(k) ? ks.filter((x) => x !== k) : [...ks, k]));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Show only">
        <button onClick={() => setKinds([])} aria-pressed={kinds.length === 0}
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${kinds.length === 0 ? 'border-ink bg-ink text-white' : 'border-slate-300 bg-white'}`}>
          All
        </button>
        {(Object.keys(KIND_LABEL) as TimelineKind[]).map((k) => (
          <button key={k} onClick={() => toggle(k)} aria-pressed={kinds.includes(k)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${kinds.includes(k) ? 'border-ink bg-ink text-white' : 'border-slate-300 bg-white'}`}>
            {KIND_LABEL[k]}
          </button>
        ))}
      </div>

      {err != null && <LoadError error={err} onRetry={load} />}
      {items === null && err == null && <Loading />}
      {items && items.length === 0 && <EmptyState title="Nothing in this period" text="Calls, emails, notes, tasks and chat show here as they happen." />}
      {items && items.length > 0 && (
        <ol className="card divide-y">
          {items.map((i, n) => (
            <li key={`${i.kind}-${i.at}-${n}`} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3 px-4 py-3">
              <div className="text-xs text-slate-500">
                <div className="font-semibold text-slate-700">{i.time}</div>
                {fmtDay(i.day)}
              </div>
              <div>
                <p className={`text-sm font-semibold ${KIND_COLOUR[i.kind]}`}>{i.title}</p>
                {i.text && <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-700">{i.text}</p>}
              </div>
            </li>
          ))}
        </ol>
      )}
      {next && (
        <button className="btn-ghost w-full" onClick={loadMore} disabled={more}>{more ? 'Loading…' : 'Load more'}</button>
      )}
    </div>
  );
}

function Tasks({ url }: { url: string }) {
  const { data, err, load } = useLoad<Task[]>(url);
  if (err) return <LoadError error={err} onRetry={load} />;
  if (!data) return <Loading />;
  if (data.length === 0) return <EmptyState title="No tasks" text="Open tasks, and tasks finished in this period, show here." />;
  return (
    <div className="card overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="bg-sky-50/70 text-xs font-semibold text-slate-600">
          <tr><th className="px-4 py-3">Task</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Due</th><th className="px-4 py-3">Outcome</th></tr>
        </thead>
        <tbody className="divide-y">
          {data.map((t) => (
            <tr key={t.id}>
              <td className="px-4 py-3 font-medium">{t.title}</td>
              <td className="px-4 py-3"><Pill value={t.overdue ? 'overdue' : t.status} /></td>
              <td className="px-4 py-3 text-slate-600">{t.due_at ? fmtDay(t.due_at.slice(0, 10)) : '–'}</td>
              <td className="px-4 py-3 text-slate-700">{t.outcome || '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Attendance({ base }: { base: string }) {
  const today = todayIST();
  const [ym, setYm] = useState(today.slice(0, 7)); // "2026-11"
  const [y, m] = ym.split('-').map(Number);
  const { data, err, load } = useLoad<MonthView>(`${base}/attendance?year=${y}&month=${m}`);
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm">Month
        <input type="month" value={ym} max={today.slice(0, 7)} onChange={(e) => e.target.value && setYm(e.target.value)} className="input w-auto py-1 text-xs" />
      </label>
      {err != null && <LoadError error={err} onRetry={load} />}
      {!data && err == null && <Loading />}
      {data && (
        <>
          <p className="text-sm text-slate-600">
            {data.month_name} {data.year} · {data.shift.name} ({data.shift.hours}) · {data.total_hours} h worked
          </p>
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead className="bg-sky-50/70 text-xs font-semibold text-slate-600">
                <tr><th className="px-4 py-3">Day</th><th className="px-4 py-3">State</th><th className="px-4 py-3">In</th><th className="px-4 py-3">Out</th><th className="px-4 py-3">Hours</th></tr>
              </thead>
              <tbody className="divide-y">
                {data.days.map((d) => (
                  <tr key={d.day}>
                    <td className="px-4 py-2">{fmtDay(d.day)}</td>
                    <td className="px-4 py-2"><Pill value={d.state} /></td>
                    <td className="px-4 py-2">{d.check_in ?? '–'}</td>
                    <td className="px-4 py-2">{d.check_out ?? '–'}</td>
                    <td className="px-4 py-2">{d.hours || '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

