'use client';
// My activity: the same view admins see on Team work, for my own data only (the server uses my login,
// never an id from the page). Plus "Connect extension": a one-time code for the KJS browser extension.
import { useCallback, useEffect, useState } from 'react';
import { fmtIST, PageTitle, Pill } from '@/components/portal/ui';
import WorkView from '@/components/portal/WorkView';
import { api, ApiFailure, type ExtensionDevice } from '@/lib/api';

export default function MyWork() {
  return (
    <div className="space-y-6">
      <PageTitle title="My activity" sub="Your calls, emails, notes, tasks, chat, sites and attendance. Only you and people allowed to see Team work can see this." />
      <ConnectExtension />
      <WorkView base="/work/me" />
    </div>
  );
}

function ConnectExtension() {
  const [devices, setDevices] = useState<ExtensionDevice[] | null>(null);
  const [code, setCode] = useState<{ code: string; expires_in_minutes: number } | null>(null);
  const [err, setErr] = useState('');
  const load = useCallback(() => { api<ExtensionDevice[]>('/monitor/extension/devices').then(setDevices).catch(() => setDevices([])); }, []);
  useEffect(load, [load]);
  const active = (devices ?? []).filter((d) => !d.disabled);

  async function getCode() {
    setErr('');
    try {
      setCode(await api('/monitor/extension/code', { method: 'POST' }));
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not get a code.');
    }
  }
  async function off(id: number) {
    await api(`/monitor/extension/devices/${id}/disable`, { method: 'POST' }).catch(() => {});
    load();
  }

  return (
    <section className="card space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Browser extension</h2>
          <p className="text-sm text-slate-600">
            {active.length ? 'Connected. Sites and idle time are recorded while you are checked in.' : 'You haven\u2019t connected the KJS Chrome extension yet (or it is under maintenance).'}
          </p>
        </div>
        <button className="btn-dark" onClick={getCode}>Connect extension</button>
      </div>
      {code && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 text-sm">
          <p>Open the KJS extension and paste this code. It works once, for {code.expires_in_minutes} minutes:</p>
          <p className="mt-2 select-all font-mono text-xl font-bold tracking-widest">{code.code}</p>
        </div>
      )}
      {err && <p role="alert" className="text-sm text-red-700">{err}</p>}
      {(devices ?? []).length > 0 && (
        <ul className="divide-y text-sm">
          {(devices ?? []).map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-3 py-2">
              <span className="font-medium">{d.name || 'Browser'}</span>
              <span className="text-slate-500">{d.last_seen_at ? `last heard ${fmtIST(d.last_seen_at)}` : 'never heard from'}</span>
              {d.disabled ? <Pill value="rejected" label="Switched off" /> : (
                <button className="btn-ghost ml-auto py-1 text-xs text-red-700" onClick={() => off(d.id)}>Disconnect</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
