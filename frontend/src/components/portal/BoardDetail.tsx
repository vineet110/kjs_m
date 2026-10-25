'use client';
// One order board: steps with planned dates and time used, checklist, "mark done", files.
// Members see it all and can update their own step; managers (boards.manage) can do everything.
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api, ApiFailure, type Board } from '@/lib/api';
import FileList from './FileList';
import { fmtDay, PageTitle, Pill } from './ui';

const STATE_LABEL: Record<string, string> = { on_track: 'On track', at_risk: 'At risk', late_board: 'Late', finished: 'Finished' };

export function BoardStatePill({ state }: { state: string }) {
  return <Pill value={state === 'on_track' ? 'ok' : state === 'finished' ? 'closed' : state} label={STATE_LABEL[state] ?? state} />;
}

export function UsedBar({ pct }: { pct: number }) {
  const colour = pct >= 100 ? 'bg-red-600' : pct >= 85 ? 'bg-amber-500' : 'bg-forest';
  return (
    <div className="flex items-center gap-2" title={`${pct}% of planned time used`}>
      <div className="h-2 flex-1 overflow-hidden rounded bg-slate-100"><div className={`h-2 ${colour}`} style={{ width: `${Math.min(100, pct)}%` }} /></div>
      <span className="w-12 text-right text-xs text-slate-500">{pct}%</span>
    </div>
  );
}

export default function BoardDetail({ code, backHref }: { code: string; backHref: string }) {
  const [b, setB] = useState<Board | null>(null);
  const [err, setErr] = useState('');

  const load = useCallback(() => {
    api<Board>(`/boards/${code}`).then(setB).catch((e) => setErr(e instanceof ApiFailure ? e.message : 'Could not load.'));
  }, [code]);
  useEffect(() => {
    load();
  }, [load]);

  async function run(path: string, body?: unknown) {
    setErr('');
    try {
      setB(await api<Board>(path, { method: 'POST', body }));
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
    }
  }

  if (!b) return <p className="text-sm text-slate-500">{err || 'Loading…'}</p>;

  return (
    <div className="space-y-6">
      <Link href={backHref} className="text-sm underline">← All boards</Link>
      <PageTitle title={`${b.code} · ${b.name}`} sub={`${b.client} · ${fmtDay(b.start, true)} → deadline ${fmtDay(b.deadline, true)} · priority ${b.priority}`}>
        <BoardStatePill state={b.state} />
      </PageTitle>
      {b.notes && <p className="card p-3 text-sm text-slate-600">{b.notes}</p>}
      {err && <p className="text-sm text-red-700">{err}</p>}

      <ol className="space-y-3">
        {b.steps.map((s) => {
          const mine = b.my_step_ids.includes(s.id) || b.can_manage;
          return (
            <li key={s.id} className={`card space-y-2 p-4 ${s.status === 'active' ? 'border-forest' : ''}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-xs font-bold">{s.position}</span>
                <span className="font-semibold">{s.name}</span>
                <Pill value={s.status === 'active' ? 'doing' : s.status === 'pending' ? 'todo' : 'done'} label={s.status === 'active' ? 'running' : s.status} />
                <span className="text-xs text-slate-500">{fmtDay(s.planned_start)} → {fmtDay(s.planned_end)}{s.percent ? ` · ${s.percent}%` : s.days ? ` · ${s.days} days` : ''}</span>
                <span className="ml-auto text-xs text-slate-500">{s.members.map((m) => m.name).join(', ') || 'No members'}</span>
              </div>
              {s.status === 'active' && <UsedBar pct={s.used_pct} />}
              {s.checklist.length > 0 && (
                <ul className="space-y-1 text-sm">
                  {s.checklist.map((c, i) => (
                    <li key={i}>
                      <label className="flex items-center gap-2">
                        <input type="checkbox" checked={c.done} disabled={!mine || s.status === 'done' || b.status !== 'active'}
                          onChange={(e) => run(`/boards/${b.code}/steps/${s.id}/checklist`, { index: i, done: e.target.checked })} />
                        <span className={c.done ? 'text-slate-400 line-through' : ''}>{c.text}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              {s.task_templates.length > 0 && <p className="text-xs text-slate-500">Tasks given when the step starts: {s.task_templates.join(' · ')}</p>}
              {s.status === 'active' && mine && b.status === 'active' && (
                <button onClick={() => confirm(`Mark "${s.name}" done and start the next step?`) && run(`/boards/${b.code}/steps/${s.id}/done`)} className="btn-dark py-1">
                  Mark step done
                </button>
              )}
            </li>
          );
        })}
      </ol>

      <section className="space-y-2">
        <h2 className="text-lg font-bold">Documents</h2>
        <FileList ownerType="board" ownerId={b.code} canUpload={b.status === 'active'} />
      </section>

      {b.can_manage && b.status === 'active' && (
        <section className="card flex flex-wrap items-center gap-2 p-4">
          <span className="text-sm font-semibold">Close this board:</span>
          {(['Delivered', 'Returned', 'Cancelled'] as const).map((f) => (
            <button key={f} onClick={() => confirm(`Mark ${b.code} as ${f}?`) && run(`/boards/${b.code}/finish`, { final_status: f })} className="btn-ghost py-1">{f}</button>
          ))}
        </section>
      )}
      {b.final_status && <p className="text-sm">Final status: <b>{b.final_status}</b></p>}
    </div>
  );
}

export function BoardList({ base, boards }: { base: string; boards: import('@/lib/api').BoardSummary[] }) {
  if (boards.length === 0) return <p className="card p-6 text-sm text-slate-500">No order boards here.</p>;
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {boards.map((b) => (
        <Link key={b.code} href={`${base}/${b.code}`} className="card space-y-2 p-4 hover:border-forest">
          <div className="flex items-center gap-2">
            <span className="font-bold">{b.code}</span>
            <BoardStatePill state={b.state} />
            <span className="ml-auto text-xs text-slate-500">Deadline {fmtDay(b.deadline)}</span>
          </div>
          <p className="text-sm">{b.name} · <span className="text-slate-500">{b.client}</span></p>
          <p className="text-xs text-slate-500">Step {Math.min(b.steps_done + 1, b.steps_total)} of {b.steps_total}{b.current_step ? `: ${b.current_step}` : ''}</p>
          {b.current_used_pct !== null && <UsedBar pct={b.current_used_pct} />}
        </Link>
      ))}
    </div>
  );
}
