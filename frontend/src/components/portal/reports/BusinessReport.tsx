'use client';
// Reports > Business: native charts from real database numbers only (D6). Empty data shows zeros.
import { useCallback, useEffect, useState } from 'react';
import { Bars, C1, C2, Columns, Legend, Panel, StackedColumns } from '@/components/portal/charts';
import { fmtDay } from '@/components/portal/ui';
import { api } from '@/lib/api';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

type Data = {
  leads_per_week: { week: string; count: number }[];
  leads_by_source: Record<string, number>; leads_by_status: Record<string, number>; leads_by_outcome: Record<string, number>;
  sla: { answered: number; on_time: number; breaches: number };
  // attendance, boards: null when that portal area is switched off (config/modules.ini)
  attendance: { day: string; present: number; late: number }[] | null;
  tasks_done: { name: string; done: number }[];
  attendance_days?: number; tasks_days?: number; // config/analytics.ini
  boards: { active: Record<string, number>; finished: Record<string, number> } | null;
  koko: { chats: number; buyer_chats: number; leads: number };
};

const LABEL: Record<string, string> = {
  enquiry_form: 'Enquiry form', website_offer: 'Website offer', price_sheet: 'Price sheet', spec_pdf: 'Spec sheet', sample: 'Sample', quote: 'Quote',
  configurator: 'Configurator', koko: 'Koko chat', on_track: 'On track', at_risk: 'At risk', late_board: 'Late',
};
const nice = (k: string) => LABEL[k] ?? k.replace(/_/g, ' ');

export default function BusinessReport() {
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
  const boards = d.boards;
  const tiles = [
    { label: 'Leads answered on time', value: onTime === null ? '—' : `${onTime}%`, sub: `${d.sla.on_time} of ${d.sla.answered}, last 8 weeks` },
    { label: 'Leads that went late', value: d.sla.breaches, sub: 'over a time limit, last 8 weeks' }, // escalation_level > 0
    { label: 'Koko chats', value: d.koko.chats, sub: `${d.koko.buyer_chats} looked like buyers · ${d.koko.leads} leads` },
    ...(boards ? [{
      label: 'Active order boards',
      value: Object.values(boards.active).reduce((a, b) => a + b, 0),
      sub: Object.entries(boards.active).map(([k, v]) => `${v} ${nice(k).toLowerCase()}`).join(' · ') || 'none',
    }] : []),
  ];

  return (
    <div className="space-y-8">
      <p className="text-sm text-slate-500">Live numbers from the database. Hover a bar for its value.</p>
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
          <Columns tip="Week of" data={d.leads_per_week.map((w) => ({ label: fmtDay(w.week), value: w.count }))} />
        </Panel>
        {d.attendance && (
          <Panel title={`Attendance, last ${d.attendance_days ?? 14} days`}>
            <Legend items={[['Present', C1], ['Late', C2]]} />
            <StackedColumns data={d.attendance.map((a) => ({ label: fmtDay(a.day), a: a.present, b: a.late }))} />
          </Panel>
        )}
        <Panel title="Leads by source (all time)"><Bars data={toRows(d.leads_by_source)} /></Panel>
        <Panel title="Leads by status (all time)"><Bars data={toRows(d.leads_by_status)} /></Panel>
        <Panel title="Lead outcomes (all time)"><Bars data={toRows(d.leads_by_outcome)} /></Panel>
        <Panel title={`Tasks done per person (${d.tasks_days ?? 30} days)`}><Bars data={d.tasks_done.map((t) => ({ label: t.name, value: t.done }))} /></Panel>
      </div>
    </div>
  );
}

function toRows(o: Record<string, number>) {
  return Object.entries(o).map(([k, v]) => ({ label: nice(k), value: v })).sort((a, b) => b.value - a.value);
}

