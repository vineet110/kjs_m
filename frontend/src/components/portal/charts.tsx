'use client';
// Small native charts for the Reports page (no chart library). Real numbers only; empty data shows "No data yet".
// Colours checked with the dataviz palette validator: series green #2E8A62, second series gold #B8860B.
import { useState } from 'react';

export const C1 = '#2E8A62';
export const C2 = '#B8860B';

export function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="card space-y-3 p-4"><h2 className="font-semibold">{title}</h2>{children}</section>;
}

export function Empty() {
  return <p className="py-6 text-center text-sm text-slate-400">No data yet</p>;
}

export function Legend({ items }: { items: [string, string][] }) {
  return (
    <div className="flex gap-4 text-xs text-slate-600">
      {items.map(([l, c]) => <span key={l} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />{l}</span>)}
    </div>
  );
}

/** Horizontal bars with the value written at the end (direct labels). */
export function Bars({ data }: { data: { label: string; value: number }[] }) {
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

/** Vertical columns over time, with a hover tooltip and the latest value labelled. `tip`: words before the
 *  label in the tooltip ("Week of"). */
export function Columns({ data, tip = '' }: { data: { label: string; value: number }[]; tip?: string }) {
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
            {tip && `${tip} `}{data[hover].label}: <b>{data[hover].value}</b>
          </div>
        )}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-500"><span>{data[0].label}</span><span>{data[data.length - 1].label}: <b>{data[data.length - 1].value}</b></span></div>
    </div>
  );
}

/** Two stacked series per day (2px surface gap between segments). */
export function StackedColumns({ data }: { data: { label: string; a: number; b: number }[] }) {
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
