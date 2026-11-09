'use client';
// Analytics: native charts from real database numbers only (D6). Empty data shows zeros.
// Colours checked with the dataviz palette validator: series green #2E8A62, second series gold #B8860B.
import { useCallback, useEffect, useState } from 'react';
import { fmtDay, PageTitle } from '@/components/portal/ui';
import { api } from '@/lib/api';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

const C1 = '#2E8A62';
const C2 = '#B8860B';

type Data = {
  leads_per_week: { week: string; count: number }[];
  leads_by_source: Record<string, number>; leads_by_status: Record<string, number>; leads_by_outcome: Record<string, number>;
  sla: { answered: number; on_time: number; breaches: number };
  attendance: { day: string; present: number; late: number }[];
  tasks_done: { name: string; done: number }[];
  boards: { active: Record<string, number>; finished: Record<string, number> };
  koko: { chats: number; buyer_chats: number; leads: number };
};

const LABEL: Record<string, string> = {
  enquiry_form: 'Enquiry form', price_sheet: 'Price sheet', spec_pdf: 'Spec sheet', sample: 'Sample', quote: 'Quote',
  configurator: 'Configurator', koko: 'Koko chat', on_track: 'On track', at_risk: 'At risk', late_board: 'Late',
};
const nice = (k: string) => LABEL[k] ?? k.replace(/_/g, ' ');

export default function Analytics() {
  const [d, setD] = useState<Data | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const load = useCallback(() => {
    setLoadErr(null);
    api<Data>('/admin/analytics').then(setD).catch(setLoadErr);
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  if (loadErr) return <LoadError error={loadErr} onRetry={load} />;
  if (!d) return <Loading />;

  const onTime = d.sla.answered ? Math.round((d.sla.on_time / d.sla.answered) * 100) : null;
  const activeBoards = Object.values(d.boards.active).reduce((a, b) => a + b, 0);
  const tiles = [
    { label: 'Leads answered on time', value: onTime === null ? '—' : `${onTime}%`, sub: `${d.sla.on_time} of ${d.sla.answered}, last 8 weeks` },
    { label: 'SLA alerts sent', value: d.sla.breaches, sub: 'last 8 weeks' },
    { label: 'Koko chats', value: d.koko.chats, sub: `${d.koko.buyer_chats} looked like buyers · ${d.koko.leads} leads` },
    { label: 'Active order boards', value: activeBoards, sub: Object.entries(d.boards.active).map(([k, v]) => `${v} ${nice(k).toLowerCase()}`).join(' · ') || 'none' },
  ];

  return (
    <div className="space-y-8">
      <PageTitle title="Analytics" sub="Live numbers from the database. Hover a bar for its value." />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map((t) => (
          <div key={t.label} className="card p-4">
            <p className="text-xs font-semibold uppercase text-slate-500">{t.label}</p>
            <p className="mt-1 text-3xl font-bold">{t.value}</p>
            <p className="text-xs text-slate-500">{t.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="New leads per week">
          <Columns data={d.leads_per_week.map((w) => ({ label: fmtDay(w.week), value: w.count }))} />
        </Panel>
        <Panel title="Attendance, last 14 days">
          <Legend items={[['Present', C1], ['Late', C2]]} />
          <StackedColumns data={d.attendance.map((a) => ({ label: fmtDay(a.day), a: a.present, b: a.late }))} />
        </Panel>
        <Panel title="Leads by source"><Bars data={toRows(d.leads_by_source)} /></Panel>
        <Panel title="Leads by status"><Bars data={toRows(d.leads_by_status)} /></Panel>
        <Panel title="Lead outcomes"><Bars data={toRows(d.leads_by_outcome)} /></Panel>
        <Panel title="Tasks done per person (30 days)"><Bars data={d.tasks_done.map((t) => ({ label: t.name, value: t.done }))} /></Panel>
      </div>
    </div>
  );
}

function toRows(o: Record<string, number>) {
  return Object.entries(o).map(([k, v]) => ({ label: nice(k), value: v })).sort((a, b) => b.value - a.value);
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="card space-y-3 p-4"><h2 className="font-semibold">{title}</h2>{children}</section>;
}

function Empty() {
  return <p className="py-6 text-center text-sm text-slate-400">No data yet</p>;
}

function Legend({ items }: { items: [string, string][] }) {
  return (
    <div className="flex gap-4 text-xs text-slate-600">
      {items.map(([l, c]) => <span key={l} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />{l}</span>)}
    </div>
  );
}

/** Horizontal bars with the value written at the end (direct labels). */
function Bars({ data }: { data: { label: string; value: number }[] }) {
  if (!data.length || data.every((x) => !x.value)) return <Empty />;
  const max = Math.max(...data.map((x) => x.value));
  return (
    <ul className="space-y-2" role="table">
      {data.map((x) => (
        <li key={x.label} className="grid grid-cols-[8rem_1fr_2.5rem] items-center gap-2 text-sm" role="row" title={`${x.label}: ${x.value}`}>
          <span className="truncate capitalize text-slate-600" role="cell">{x.label}</span>
          <span className="h-3" role="presentation"><span className="block h-3 rounded-r" style={{ width: `${Math.max(2, (x.value / max) * 100)}%`, background: C1 }} /></span>
          <span className="text-right font-semibold" role="cell">{x.value}</span>
        </li>
      ))}
    </ul>
  );
}

/** Vertical columns over time, with a hover tooltip and the latest value labelled. */
function Columns({ data }: { data: { label: string; value: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (data.every((x) => !x.value)) return <Empty />;
  const max = Math.max(1, ...data.map((x) => x.value));
  return (
    <div>
      <div className="relative flex h-40 items-end gap-1 border-b border-slate-200">
        {data.map((x, i) => (
          <div key={x.label} className="flex h-full flex-1 items-end justify-center" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <div className="w-full max-w-[28px] rounded-t" style={{ height: `${(x.value / max) * 100}%`, minHeight: x.value ? 3 : 0, background: C1, opacity: hover === null || hover === i ? 1 : 0.5 }} />
          </div>
        ))}
        {hover !== null && (
          <div className="pointer-events-none absolute -top-2 left-1/2 -translate-x-1/2 rounded bg-ink px-2 py-1 text-xs text-white">
            Week of {data[hover].label}: <b>{data[hover].value}</b>
          </div>
        )}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-500"><span>{data[0].label}</span><span>{data[data.length - 1].label}: <b>{data[data.length - 1].value}</b></span></div>
    </div>
  );
}

/** Two stacked series per day (2px surface gap between segments). */
function StackedColumns({ data }: { data: { label: string; a: number; b: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (data.every((x) => !x.a && !x.b)) return <Empty />;
  const max = Math.max(1, ...data.map((x) => x.a + x.b));
  return (
    <div>
      <div className="relative flex h-40 items-end gap-1 border-b border-slate-200">
        {data.map((x, i) => (
          <div key={x.label} className="flex h-full flex-1 flex-col items-center justify-end gap-[2px]" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            {x.b > 0 && <div className="w-full max-w-[22px] rounded-t" style={{ height: `${(x.b / max) * 100}%`, background: C2 }} />}
            {x.a > 0 && <div className={`w-full max-w-[22px] ${x.b ? '' : 'rounded-t'}`} style={{ height: `${(x.a / max) * 100}%`, background: C1 }} />}
          </div>
        ))}
        {hover !== null && (
          <div className="pointer-events-none absolute -top-2 left-1/2 -translate-x-1/2 rounded bg-ink px-2 py-1 text-xs text-white">
            {data[hover].label}: {data[hover].a} present · {data[hover].b} late
          </div>
        )}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-500"><span>{data[0].label}</span><span>{data[data.length - 1].label}</span></div>
    </div>
  );
}
