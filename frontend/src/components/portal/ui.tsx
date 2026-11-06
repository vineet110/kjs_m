// Small shared bits for portal screens. Status colours always come with a text label.
import { Icon, type IconName } from './icons';

const PILL: Record<string, string> = {
  present: 'bg-emerald-100 text-emerald-800', late: 'bg-emerald-100 text-emerald-800', absent: 'bg-red-100 text-red-700',
  leave: 'bg-sky-100 text-sky-800', half_day: 'bg-amber-100 text-amber-800', holiday: 'bg-violet-100 text-violet-800', off: 'bg-slate-100 text-slate-500',
  not_joined: 'bg-slate-100 text-slate-400',
  upcoming: 'bg-white text-slate-400 ring-1 ring-slate-200', pending: 'bg-amber-100 text-amber-800',
  approved: 'bg-emerald-100 text-emerald-800', rejected: 'bg-red-100 text-red-700',
  casual: 'bg-blue-100 text-blue-800', sick: 'bg-rose-100 text-rose-800', earned: 'bg-amber-100 text-amber-800', unpaid: 'bg-slate-200 text-slate-700',
  new: 'bg-amber-100 text-amber-800', contacted: 'bg-sky-100 text-sky-800', closed: 'bg-slate-200 text-slate-700',
  ok: 'bg-emerald-100 text-emerald-800', due_soon: 'bg-amber-100 text-amber-800', overdue: 'bg-red-100 text-red-700',
  todo: 'bg-slate-100 text-slate-700', doing: 'bg-sky-100 text-sky-800', done: 'bg-emerald-100 text-emerald-800',
  active: 'bg-emerald-100 text-emerald-800', at_risk: 'bg-amber-100 text-amber-800', late_board: 'bg-red-100 text-red-700',
};

export function Pill({ value, label }: { value: string; label?: string }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold capitalize ${PILL[value] ?? 'bg-slate-100 text-slate-700'}`}>
      {label ?? value.replace(/_/g, ' ')}
    </span>
  );
}

export function PageTitle({ title, sub, children }: { title: string; sub?: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold">{title}</h1>
        {sub && <p className="text-sm text-slate-500">{sub}</p>}
      </div>
      {children}
    </div>
  );
}

/** "Mon 26 Oct" from "2026-10-26" (date only, no time zone shift). */
export function fmtDay(iso: string, withYear = false) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short', ...(withYear ? { year: 'numeric' } : {}), timeZone: 'UTC',
  });
}

/** IST date-time for a UTC timestamp from the API. */
export function fmtIST(iso: string) {
  return new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' });
}

export function todayIST() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' }); // YYYY-MM-DD
}

export function addDays(iso: string, n: number) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}

export function Msg({ msg }: { msg: { ok: boolean; text: string } | null }) {
  if (!msg) return null;
  return <p className={`rounded p-2 text-sm ${msg.ok ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-700'}`}>{msg.text}</p>;
}

/** A friendly "nothing here" box: an icon, a short title and one line of help (instead of a bare grey
 * sentence). `tone="done"` = a good thing (nothing waiting): green tick. */
export function EmptyState({ title, text, icon = 'inbox', tone = 'plain' }: {
  title: string; text?: string; icon?: IconName; tone?: 'plain' | 'done';
}) {
  return (
    <div className="card flex flex-col items-center gap-2 px-4 py-8 text-center animate-in fade-in duration-300 motion-reduce:animate-none">
      <span className={`flex h-12 w-12 items-center justify-center rounded-full ${tone === 'done' ? 'bg-emerald-50 text-emerald-600' : 'bg-stone-100 text-stone-400'}`}>
        <Icon name={tone === 'done' ? 'check' : icon} className="h-6 w-6" />
      </span>
      <p className="font-semibold text-stone-800">{title}</p>
      {text && <p className="max-w-sm text-sm text-stone-500">{text}</p>}
    </div>
  );
}
