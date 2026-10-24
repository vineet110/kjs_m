'use client';
// Top of "My day" and the attendance page: check in / out + "receiving tasks" switch.
import { useCallback, useEffect, useState } from 'react';
import { api, ApiFailure, type Today } from '@/lib/api';
import { Pill } from './ui';

export default function TodayCard({ onChange }: { onChange?: () => void }) {
  const [t, setT] = useState<Today | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<Today>('/attendance/today').then(setT).catch(() => setErr('Could not load attendance.'));
  }, []);
  useEffect(() => {
    load();
  }, [load]);

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

  if (!t) return <div className="card p-4 text-sm text-slate-500">{err || 'Loading attendance…'}</div>;

  return (
    <div className="card flex flex-wrap items-center gap-4 p-4">
      <div className="min-w-[10rem]">
        <p className="text-xs font-semibold uppercase text-slate-500">Today · shift {t.shift}</p>
        <p className="mt-1 text-sm">
          {t.check_in ? <>In <b>{t.check_in}</b>{t.check_out && <> · Out <b>{t.check_out}</b> · {t.hours} h</>}</> : 'Not checked in yet'}
          {t.status && <span className="ml-2"><Pill value={t.status} /></span>}
        </p>
      </div>
      <div className="flex gap-2">
        {!t.check_in && <button disabled={busy} onClick={() => act('/attendance/check-in')} className="btn-dark">Check in</button>}
        {t.check_in && !t.check_out && <button disabled={busy} onClick={() => act('/attendance/check-out')} className="btn-ghost">Check out</button>}
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
          className={`relative h-6 w-11 rounded-full transition-colors ${t.is_available ? 'bg-forest' : 'bg-slate-300'}`}
        >
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${t.is_available ? 'left-[22px]' : 'left-0.5'}`} />
        </button>
      </label>
      {err && <p className="w-full text-sm text-red-700">{err}</p>}
    </div>
  );
}
