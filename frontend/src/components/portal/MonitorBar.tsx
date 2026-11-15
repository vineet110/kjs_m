'use client';
// The strip under the portal header while checked in: screen sharing, breaks, and the idle warning.
// Asks the server every minute (/monitor/state); the server decides, this only shows it. Hidden when the
// `monitoring` area is off (the portal frame doesn't render it then).
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { api, ApiFailure, type MonitorState } from '@/lib/api';
import { applyState, getStatus, startSharing, subscribe } from '@/lib/monitor';

const POLL_MS = 60 * 1000;

export default function MonitorBar() {
  const [st, setSt] = useState<MonitorState | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const sharing = useSyncExternalStore(subscribe, getStatus, () => 'off' as const);

  const load = useCallback(() => {
    api<MonitorState>('/monitor/state')
      .then((s) => { setSt(s); applyState(s); })
      .catch(() => {}); // area off or offline: show nothing rather than a broken bar
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(() => { if (document.visibilityState === 'visible') load(); }, POLL_MS);
    const again = () => load(); // check-in / check-out happened on this page
    window.addEventListener('kjs:attendance-changed', again);
    return () => { clearInterval(t); window.removeEventListener('kjs:attendance-changed', again); };
  }, [load]);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setErr('');
    try {
      await fn();
      load();
    } catch (e) {
      setErr(e instanceof ApiFailure || e instanceof Error ? e.message : 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  }

  if (!st || !st.checked_in) return null;
  const used = st.break_minutes_today;
  const limit = st.config.break_minutes_per_day;

  return (
    <>
      <div role="status" className={`flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-4 py-2 text-sm ${st.on_break ? 'border-sky-200 bg-sky-50 text-sky-900' : sharing === 'sharing' || sharing === 'phone' ? 'border-stone-200 bg-white text-slate-700' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
        {st.on_break ? (
          <span className="font-semibold">On a break · {used} of {limit} min used today. Screenshots are paused.</span>
        ) : sharing === 'sharing' ? (
          <span>Screen shared · a screenshot every {st.config.screenshot_minutes} min</span>
        ) : sharing === 'phone' ? (
          <span>On a phone: nothing is tracked. Use your laptop if you can.</span>
        ) : sharing === 'unsupported' ? (
          <span className="font-semibold">This browser can&apos;t share the screen. Please use Chrome or Edge on your laptop.</span>
        ) : (
          <span className="font-semibold">
            {sharing === 'refused' ? 'Screen sharing was refused.' : sharing === 'stopped' ? 'Screen sharing stopped.' : 'Your screen isn’t being shared.'}{' '}
            Admins are told if it stays off.
          </span>
        )}
        <span className="ml-auto flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500">{st.extension === 'connected' ? 'Extension connected' : 'Extension not connected'}</span>
          {!st.on_break && sharing !== 'sharing' && sharing !== 'phone' && sharing !== 'unsupported' && (
            <button disabled={busy} onClick={() => run(startSharing)} className="btn-dark py-1 text-xs">Share screen</button>
          )}
          {st.on_break ? (
            <button disabled={busy} onClick={() => run(() => api('/monitor/break/end', { method: 'POST' }))} className="btn-dark py-1 text-xs">End break</button>
          ) : (
            <button disabled={busy} onClick={() => run(() => api('/monitor/break/start', { method: 'POST' }))} className="btn-ghost py-1 text-xs">Take a break</button>
          )}
        </span>
        {err && <span role="alert" className="w-full text-xs text-red-700">{err}</span>}
      </div>
      {st.idle && !st.idle.reason && <IdleWarning idle={st.idle} warn={st.config.idle_warn_minutes} onDone={load} />}
    </>
  );
}

/** "No activity for 15 minutes": the employee says why (the extension ends the idle period on activity). */
function IdleWarning({ idle, warn, onDone }: { idle: NonNullable<MonitorState['idle']>; warn: number; onDone: () => void }) {
  const [other, setOther] = useState(false);
  const [note, setNote] = useState('');
  const [err, setErr] = useState('');
  async function say(reason: 'call' | 'meeting' | 'other') {
    setErr('');
    try {
      await api(`/monitor/idle/${idle.id}/reason`, { method: 'POST', body: { reason, note } });
      onDone();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
    }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div role="alertdialog" aria-modal="true" aria-labelledby="idle-title" className="card w-full max-w-md space-y-3 border-2 border-amber-500 p-5">
        <h2 id="idle-title" className="text-lg font-bold">No activity for {Math.max(warn, idle.minutes)} minutes</h2>
        <p className="text-sm text-slate-600">This will be reported to admin soon. Please take action. What are you doing?</p>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={() => say('call')}>On a call</button>
          <button className="btn-ghost" onClick={() => say('meeting')}>In a meeting</button>
          <button className="btn-ghost" onClick={() => setOther(true)}>Other…</button>
        </div>
        {other && (
          <div className="space-y-2">
            <label htmlFor="idle-note" className="block text-sm font-medium">What were you doing?</label>
            <input id="idle-note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} className="input" />
            <button className="btn-dark" disabled={!note.trim()} onClick={() => say('other')}>Save</button>
          </div>
        )}
        {err && <p role="alert" className="text-sm text-red-700">{err}</p>}
      </div>
    </div>
  );
}
