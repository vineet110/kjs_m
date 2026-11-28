'use client';
// Laptop monitoring: unlock requests waiting on me, live status and open alerts of the people I may see
// (admins: everyone; managers: the people who report to them). Each section reloads the moment the monitoring
// server pushes a change (lib/monitoring.ts), and every refresh_seconds anyway.
import { useCallback, useEffect, useRef, useState } from 'react';
import { EmptyState, fmtIST, PageTitle, Pill } from '@/components/portal/ui';
import { useMe } from '@/components/portal/PortalShell';
import { useToast } from '@/components/portal/Toast';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';
import { api, ApiFailure } from '@/lib/api';
import { canSee } from '@/lib/modules';
import { minutes, stateLabel, useMonitorChanges, type Change, type LivePerson, type MonitorAlert, type UnlockRequest } from '@/lib/monitoring';
import { pokeUpdates } from '@/lib/updates';

const STATE_PILL: Record<string, string> = { WORKING: 'active', BREAK: 'due_soon', LOCKED: 'overdue', OFF_DUTY: 'off', NO_DEVICE: 'not_joined' };
const ALERT_LABEL: Record<string, string> = {
  'lock.requested': 'Unlock requested', 'lock.escalated': 'Unlock still waiting', 'lock.rejected': 'Unlock rejected',
  'agent.offline': 'Laptop offline', 'agent.tampered': 'Monitoring switched off?', 'crm.sync_failed': 'Attendance link down',
};

/** Loads `path` now and whenever one of `kinds` changes. Only the newest answer counts. */
function useLive<T>(path: string, kinds: Change[], enabled: boolean) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const latest = useRef(0);
  const load = useCallback(() => {
    const mine = ++latest.current;
    api<T>(path).then((d) => { if (mine === latest.current) { setData(d); setErr(null); } })
      .catch((e) => { if (mine === latest.current) setErr(e); });
  }, [path]);
  useEffect(() => { if (enabled) load(); }, [enabled, load]);
  useMonitorChanges(kinds, load, enabled);
  return { data, err, load };
}

export default function MonitoringPage() {
  const me = useMe();
  const on = canSee(me, 'monitoring');
  const mayView = on && me.permissions.includes('monitoring.view');
  const mayApprove = on && me.permissions.includes('monitoring.approve');
  const unlocks = useLive<{ requests: UnlockRequest[] }>('/monitoring/unlock-requests', ['unlock'], mayApprove);
  const live = useLive<{ employees: LivePerson[] }>('/monitoring/live', ['live'], mayView);
  const alerts = useLive<{ alerts: MonitorAlert[] }>('/monitoring/alerts?open_only=true', ['alerts'], mayView);

  if (!on) return <EmptyState title="Laptop monitoring is not switched on yet" />;
  const scope = me.role === 'admin' ? 'everyone' : 'the people who report to you';
  return (
    <div className="space-y-6">
      <PageTitle title="Laptop monitoring" sub={`Live status, unlock requests and alerts for ${scope}. Updates the moment something changes.`} />
      {mayApprove && <Unlocks state={unlocks} />}
      {mayView && <Live state={live} />}
      {mayView && <Alerts state={alerts} />}
    </div>
  );
}

type Loaded<T> = { data: T | null; err: unknown; load: () => void };

function Unlocks({ state }: { state: Loaded<{ requests: UnlockRequest[] }> }) {
  const toast = useToast();
  const [busy, setBusy] = useState<number | null>(null);
  const [comment, setComment] = useState<Record<number, string>>({});
  const decide = (r: UnlockRequest, decision: 'approved' | 'rejected') => {
    setBusy(r.id);
    api(`/monitoring/unlock-requests/${r.id}/decision`, { method: 'POST', body: { decision, comment: comment[r.id] || null } })
      .then(() => { toast(decision === 'approved' ? `${r.name}'s laptop is unlocking` : 'Unlock rejected'); state.load(); pokeUpdates(); })
      .catch((e) => toast(e instanceof ApiFailure ? e.body.message : 'Could not save. Try again.', 'error'))
      .finally(() => setBusy(null));
  };
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-bold">Unlock requests waiting</h2>
      {state.err ? <LoadError error={state.err} onRetry={state.load} /> : !state.data ? <Loading /> :
        state.data.requests.length === 0 ? <EmptyState title="Nothing waiting" tone="done" /> : (
          <div className="card divide-y">
            {state.data.requests.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center gap-3 p-3 text-sm">
                <div className="min-w-48 flex-1">
                  <p className="font-semibold">{r.name} {r.escalated && <Pill value="overdue" label="escalated" />}</p>
                  <p className="text-slate-500">
                    {r.hostname} · closed {fmtIST(r.closed_at)}, opened {fmtIST(r.reopened_at)} ({minutes(r.working_gap_min)} of working time)
                  </p>
                  <p>Reason: <span className="font-medium">{r.reason_code}</span>{r.reason_text ? ` - ${r.reason_text}` : ''}</p>
                </div>
                <input className="input w-56" placeholder="Comment (optional)" maxLength={1000} value={comment[r.id] ?? ''}
                  onChange={(e) => setComment({ ...comment, [r.id]: e.target.value })} aria-label={`Comment for ${r.name}`} />
                <button className="btn-dark" disabled={busy === r.id} onClick={() => decide(r, 'approved')}>Approve</button>
                <button className="btn-ghost" disabled={busy === r.id} onClick={() => decide(r, 'rejected')}>Reject</button>
              </div>
            ))}
          </div>
        )}
    </section>
  );
}

function Live({ state }: { state: Loaded<{ employees: LivePerson[] }> }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-bold">Live status</h2>
      {state.err ? <LoadError error={state.err} onRetry={state.load} /> : !state.data ? <Loading /> :
        state.data.employees.length === 0 ? <EmptyState title="No one to show yet" text="People appear here once their laptop is enrolled." /> : (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500"><tr><th className="p-3">Name</th><th className="p-3">Department</th><th className="p-3">State</th><th className="p-3">Laptop</th><th className="p-3">Last seen</th></tr></thead>
              <tbody className="divide-y">
                {state.data.employees.map((p) => {
                  const d = p.devices[0];
                  return (
                    <tr key={p.employee_id}>
                      <td className="p-3 font-medium">{p.name}</td>
                      <td className="p-3">{p.department ?? '-'}</td>
                      <td className="p-3"><Pill value={STATE_PILL[p.status] ?? 'off'} label={stateLabel(p.status)} /></td>
                      <td className="p-3">{d ? `${d.hostname} · ${p.online ? 'online' : 'offline'}` : '-'}</td>
                      <td className="p-3 text-slate-500">{d?.last_seen_at ? `${fmtIST(d.last_seen_at)} IST` : '-'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
    </section>
  );
}

function Alerts({ state }: { state: Loaded<{ alerts: MonitorAlert[] }> }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-bold">Open alerts</h2>
      {state.err ? <LoadError error={state.err} onRetry={state.load} /> : !state.data ? <Loading /> :
        state.data.alerts.length === 0 ? <EmptyState title="No open alerts" tone="done" /> : (
          <div className="card divide-y">
            {state.data.alerts.map((a) => (
              <div key={a.id} className="flex flex-wrap items-center gap-2 p-3 text-sm">
                <Pill value={a.type.startsWith('lock') ? 'overdue' : 'due_soon'} label={ALERT_LABEL[a.type] ?? a.type} />
                <span className="font-medium">{a.name ?? 'Monitoring server'}</span>
                <span className="ml-auto text-xs text-slate-400">{fmtIST(a.created_at)} IST</span>
              </div>
            ))}
          </div>
        )}
    </section>
  );
}
