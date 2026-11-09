'use client';
// Alerts: the rules (from config/alerts.ini and config/sla.ini) and the log of alerts sent.
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { fmtIST, PageTitle, Pill } from '@/components/portal/ui';
import { api } from '@/lib/api';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

type Alerts = {
  rules: { board_thresholds: number[]; channels: string[]; sla: { respond_minutes: number; resolve_minutes: number; escalate_after_minutes: number } };
  log: { kind: string; title: string; body: string; link: string; at: string; people: number }[];
};

export default function AlertsPage() {
  const [a, setA] = useState<Alerts | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const load = useCallback(() => {
    setLoadErr(null);
    api<Alerts>('/admin/alerts').then(setA).catch(setLoadErr);
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  if (loadErr) return <LoadError error={loadErr} onRetry={load} />;
  if (!a) return <Loading />;
  const r = a.rules;
  return (
    <div className="space-y-6">
      <PageTitle title="Alerts" sub="Rules live in config/alerts.ini and config/sla.ini (see Settings). Changes apply within seconds." />
      <div className="grid gap-3 md:grid-cols-3">
        <div className="card p-4 text-sm"><p className="font-semibold">Order boards</p><p>Alert when a step has used {r.board_thresholds.join('%, ')}% of its time.</p></div>
        <div className="card p-4 text-sm"><p className="font-semibold">Leads</p><p>Respond in {r.sla.respond_minutes} min, close in {r.sla.resolve_minutes} min. Admins are told {r.sla.escalate_after_minutes} min after a miss.</p></div>
        <div className="card p-4 text-sm"><p className="font-semibold">Sent by</p><p>{r.channels.join(', ').replace('in_app', 'bell in the portal')}. WhatsApp after Meta verification.</p></div>
      </div>
      <section className="space-y-2">
        <h2 className="text-lg font-bold">Alerts sent</h2>
        <div className="card divide-y">
          {a.log.length === 0 && <p className="p-4 text-sm text-slate-500">No alerts yet.</p>}
          {a.log.map((x, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2 p-3 text-sm">
              <Pill value={x.kind === 'board.alert' ? 'at_risk' : 'overdue'} label={x.kind === 'board.alert' ? 'order board' : 'lead SLA'} />
              {x.link ? <Link href={x.link} className="font-medium underline">{x.title}</Link> : <span className="font-medium">{x.title}</span>}
              <span className="text-slate-500">{x.body}</span>
              <span className="ml-auto text-xs text-slate-400">{fmtIST(x.at)} IST · {x.people} {x.people === 1 ? 'person' : 'people'}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
