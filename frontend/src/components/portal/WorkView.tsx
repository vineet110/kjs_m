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
  api, type MonthView, type ScreenshotDay, type Task, type Timeline, type TimelineItem, type TimelineKind, type WorkOverview,
} from '@/lib/api';

type Tab = 'overview' | 'timeline' | 'screenshots' | 'tasks' | 'attendance';
const TABS: { id: Tab; label: string; admin?: boolean }[] = [
  { id: 'overview', label: 'Overview' }, { id: 'timeline', label: 'Timeline' },
  { id: 'screenshots', label: 'Screenshots', admin: true },
  { id: 'tasks', label: 'Tasks' }, { id: 'attendance', label: 'Attendance' },
];

/** admin: Team work (shows Screenshots); My work never does (employees don't see screenshots). */
export default function WorkView({ base, onPerson, admin = false }: { base: string; onPerson?: (o: WorkOverview) => void; admin?: boolean }) {
  const [tab, setTab] = useState<Tab>('overview');
  const [from, setFrom] = useState(todayIST());
  const [to, setTo] = useState(todayIST());
  const range = `from=${from}&to=${to}`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div role="tablist" aria-label="Work sections" className="flex gap-1 overflow-x-auto overflow-y-hidden border-b">
          {TABS.filter((t) => admin || !t.admin).map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
              className={`-mb-px shrink-0 border-b-2 px-4 py-2 text-sm font-semibold ${tab === t.id ? 'border-gold text-ink' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
              {t.label}
            </button>
          ))}
        </div>
        {tab !== 'attendance' && tab !== 'screenshots' && (
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
      {tab === 'screenshots' && admin && <Screenshots base={base} />}
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
        <StatTile label="Break minutes" value={t.break_minutes} icon="clock" tone="blue" />
        <StatTile label="Idle minutes" value={t.idle_minutes} icon="clock" tone="slate"
          hint={data.extension === 'not_connected' ? 'Extension not connected' : undefined} />
        <StatTile label="Screenshots" value={t.screenshots} icon="file" tone="slate" />
      </div>
      {data.extension === 'not_connected' && (
        <p className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600">
          Browser extension not connected (or currently under maintenance). Idle time and Sites show here once it is.
        </p>
      )}
    </div>
  );
}

const KIND_LABEL: Record<TimelineKind, string> = {
  call: 'Calls', email: 'Emails', note: 'Notes', outcome: 'Lead outcomes', task: 'Tasks', chat: 'Chat', attendance: 'Check-in / out',
  break: 'Breaks', idle: 'Idle', screen: 'Screen sharing',
};
const KIND_COLOUR: Record<TimelineKind, string> = {
  call: 'text-sky-800', email: 'text-sky-800', note: 'text-slate-800', outcome: 'text-emerald-800',
  task: 'text-emerald-800', chat: 'text-violet-800', attendance: 'text-amber-800',
  break: 'text-sky-800', idle: 'text-amber-800', screen: 'text-red-700',
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


/** Screenshots of one day (admins only). Images come through a permission-checked route, never a public link. */
function Screenshots({ base }: { base: string }) {
  const [day, setDay] = useState(todayIST());
  const { data, err, load } = useLoad<ScreenshotDay>(`${base}/screenshots?day=${day}`);
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-1 text-xs">
        <button className="btn-ghost py-1" aria-label="Previous day" onClick={() => setDay(addDays(day, -1))}>←</button>
        <input type="date" value={day} max={todayIST()} onChange={(e) => e.target.value && setDay(e.target.value)} className="input w-auto py-1 text-xs" />
        <button className="btn-ghost py-1" aria-label="Next day" disabled={day >= todayIST()} onClick={() => setDay(addDays(day, 1))}>→</button>
      </div>
      {err != null && <LoadError error={err} onRetry={load} />}
      {!data && err == null && <Loading />}
      {data && data.gaps.length > 0 && (
        <ul className="space-y-1 text-sm">
          {data.gaps.map((g, n) => (
            <li key={n} className="rounded border border-red-200 bg-red-50 px-3 py-1.5 text-red-800">
              Screen sharing {g.state} at {g.from}{g.to ? `, back at ${g.to}` : ', not shared again'}
            </li>
          ))}
        </ul>
      )}
      {data && data.screenshots.length === 0 && <EmptyState title="No screenshots this day" text="They are taken while the person is checked in and sharing the screen." />}
      {data && data.screenshots.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {data.screenshots.map((s) => (
            <button key={s.id} onClick={() => setOpen(s.id)} className="text-left">
              {/* eslint-disable-next-line @next/next/no-img-element -- private image from our API, not optimisable */}
              <img src={`/api/v1${base}/screenshots/${s.id}/image`} alt={`Screenshot at ${s.time}`} loading="lazy"
                className="aspect-video w-full rounded-lg border border-slate-200 bg-slate-100 object-cover" />
              <span className="mt-1 block text-xs text-slate-500">{s.time} · {s.size_kb} KB</span>
            </button>
          ))}
        </div>
      )}
      {open !== null && (
        <div role="dialog" aria-modal="true" aria-label="Screenshot" className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setOpen(null)}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`/api/v1${base}/screenshots/${open}/image`} alt="Screenshot, full size" className="max-h-full max-w-full rounded" />
          <button className="absolute right-4 top-4 rounded bg-white px-3 py-1 text-sm font-semibold" onClick={() => setOpen(null)}>Close</button>
        </div>
      )}
    </div>
  );
}
