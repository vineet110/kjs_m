'use client';
// Top of "My day" and the attendance page: check in / out + "receiving tasks" switch.
import { useCallback, useEffect, useState } from 'react';
import { api, ApiFailure, type Today } from '@/lib/api';
import { Pill } from './ui';
import Loading from '@/components/ui/Loading';

export default function TodayCard({
  onChange,
  onOpenLeave,
  onOpenRegularize,
}: {
  onChange?: () => void;
  onOpenLeave?: () => void;
  onOpenRegularize?: () => void;
}) {
  const [t, setT] = useState<Today | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState('');

  const load = useCallback(() => {
    api<Today>('/attendance/today').then(setT).catch(() => setErr('Could not load attendance.'));
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!t?.check_in || t.check_out) {
      setElapsed('');
      return;
    }
    const update = () => {
      const [h, m] = t.check_in!.split(':').map(Number);
      const now = new Date();
      const nowIST = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
      const checkInDate = new Date(nowIST);
      checkInDate.setHours(h, m, 0, 0);
      const diffMs = Math.max(0, nowIST.getTime() - checkInDate.getTime());
      const diffH = Math.floor(diffMs / 3600000);
      const diffM = Math.floor((diffMs % 3600000) / 60000);
      setElapsed(`${diffH}h ${diffM.toString().padStart(2, '0')}m`);
    };
    update();
    const interval = setInterval(update, 30000);
    return () => clearInterval(interval);
  }, [t?.check_in, t?.check_out]);

  async function act(path: string, body?: unknown) {
    setBusy(true);
    setErr('');
    try {
      const res = await api<Today | { is_available: boolean }>(path, { method: 'POST', body });
      if ('day' in res) setT(res);
      else setT((cur) => (cur ? { ...cur, ...res } : cur));
      onChange?.();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  }

  if (!t) return <div className="card p-4 text-sm text-slate-500">{err || <Loading />}</div>;

  return (
    <div className="card flex flex-wrap items-center gap-4 p-4">
      <div className="min-w-[12rem]">
        <p className="text-xs font-semibold uppercase text-slate-500">
          {t.shift_name ? `${t.shift_name} · ${t.shift}` : `Today · Shift ${t.shift}`}
        </p>
        <p className="mt-1 text-sm flex items-center flex-wrap gap-1.5">
          {t.check_in ? (
            <>
              In <b>{t.check_in}</b>
              {t.check_out && <> · Out <b>{t.check_out}</b> · {t.hours} h</>}
            </>
          ) : (
            'Not checked in yet'
          )}
          {t.status && <span className="ml-1"><Pill value={t.status} /></span>}
          {elapsed && (
            <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-800">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
              Active · {elapsed}
            </span>
          )}
        </p>
      </div>
      <div className="flex items-center gap-2">
        {!t.check_in && <button disabled={busy} onClick={() => act('/attendance/check-in')} className="btn-dark">Check in</button>}
        {t.check_in && !t.check_out && <button disabled={busy} onClick={() => act('/attendance/check-out')} className="btn-ghost">Check out</button>}
        {onOpenLeave && (
          <button type="button" onClick={onOpenLeave} className="btn-ghost py-1 text-xs font-medium text-slate-700">
            Apply Leave
          </button>
        )}
        {onOpenRegularize && (
          <button type="button" onClick={onOpenRegularize} className="btn-ghost py-1 text-xs font-medium text-slate-700">
            Missed Punch
          </button>
        )}
      </div>
      <label className="ml-auto flex cursor-pointer items-center gap-3 text-sm">
        <span>
          <span className="font-semibold">Receiving tasks</span>
          <span className="block text-xs text-slate-500">{t.is_available ? 'On: new work can come to you' : 'Off: no new work assigned'}</span>
        </span>
        <button
          role="switch"
          aria-checked={t.is_available}
          disabled={busy}
          onClick={() => act('/attendance/availability', { available: !t.is_available })}
          className={`relative h-6 w-11 rounded-full transition-colors ${t.is_available ? 'bg-gold' : 'bg-slate-300'}`}
        >
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${t.is_available ? 'left-[22px]' : 'left-0.5'}`} />
        </button>
      </label>
      {err && <p className="w-full text-sm text-red-700">{err}</p>}
    </div>
  );
}
