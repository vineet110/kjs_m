'use client';
// One order board: a summary, the steps as a timeline, and tabs for Steps, Files, People and History.
// Everyone on the board sees it and updates it (checklists, files). A step's people (its head
// included) or the owner mark it done. The owner (or boards.manage) changes people and finishes it.
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, ApiFailure, type Board, type BoardStep, type BoardSummary, type Colleague } from '@/lib/api';
import BoardHistory from './BoardHistory';
import FileList from './FileList';
import { Icon } from './icons';
import { useToast } from './Toast';
import { fmtDay, Pill } from './ui';
import Loading from '@/components/ui/Loading';

const STATE_LABEL: Record<string, string> = { on_track: 'On track', at_risk: 'At risk', late_board: 'Late', finished: 'Finished' };

export function BoardStatePill({ state }: { state: string }) {
  return <Pill value={state === 'on_track' ? 'ok' : state === 'finished' ? 'closed' : state} label={STATE_LABEL[state] ?? state} />;
}

export function UsedBar({ pct }: { pct: number }) {
  const colour = pct >= 100 ? 'bg-red-600' : pct >= 85 ? 'bg-amber-500' : 'bg-ink';
  return (
    <div className="flex items-center gap-2" title={`${pct}% of planned time used`}>
      <div className="h-2 flex-1 overflow-hidden rounded bg-slate-100"><div className={`h-2 ${colour}`} style={{ width: `${Math.min(100, pct)}%` }} /></div>
      <span className="w-24 text-right text-xs text-slate-500">{pct}% time used</span>
    </div>
  );
}

/** Round badge with a person's initials. */
function Avatar({ name, head = false }: { name: string; head?: boolean }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('') || '?';
  return (
    <span title={head ? `${name} (head)` : name}
      className={`relative inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${head ? 'bg-gold text-ink' : 'bg-slate-200 text-slate-700'}`}>
      {initials}
      {head && <span aria-hidden className="absolute -right-1 -top-1 text-[11px] leading-none text-gold-dark">★</span>}
    </span>
  );
}

type Tab = 'steps' | 'files' | 'people' | 'history';

export default function BoardDetail({ code, backHref }: { code: string; backHref: string }) {
  const [b, setB] = useState<Board | null>(null);
  const [err, setErr] = useState('');
  const [tab, setTab] = useState<Tab>('steps');
  const [staff, setStaff] = useState<Colleague[]>([]);
  const toast = useToast();

  const load = useCallback(() => {
    api<Board>(`/boards/${code}`).then(setB).catch((e) => setErr(e instanceof ApiFailure ? e.message : 'Could not load.'));
  }, [code]);
  useEffect(() => {
    load();
  }, [load]);
  // The staff list is only needed by people who can change who is on the board.
  const canEdit = !!b?.can_edit && b.status === 'active';
  useEffect(() => {
    if (canEdit) api<Colleague[]>('/employee/colleagues').then(setStaff).catch(() => setStaff([]));
  }, [canEdit]);

  /** Sends a change; the answer is the whole board again. Returns true when it worked. */
  async function run(path: string, init: { method: string; body?: unknown }, done?: string): Promise<boolean> {
    setErr('');
    try {
      setB(await api<Board>(path, init));
      if (done) toast(done);
      return true;
    } catch (e) {
      // Errors stay on the page (not a toast that goes away before it's read): see Toast.tsx
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
      return false;
    }
  }

  if (!b) return err ? <p className="text-sm text-slate-500">{err}</p> : <Loading />;
  const running = b.status === 'active';

  return (
    <div className="space-y-5">
      <Link href={backHref} className="text-sm underline">← All boards</Link>

      <header className="card space-y-4 p-5">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-gold-dark">{b.code}</p>
            <h1 className="text-2xl font-bold">{b.name}</h1>
            <p className="text-sm text-slate-500">
              {b.client} · {fmtDay(b.start, true)} → deadline {fmtDay(b.deadline, true)}
              {b.owner.name && <> · Owner <b className="text-slate-700">{b.owner.name}</b></>}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Pill value={b.priority === 'high' ? 'overdue' : b.priority === 'low' ? 'todo' : 'due_soon'} label={`${b.priority} priority`} />
            <BoardStatePill state={b.state} />
          </div>
        </div>
        <Timeline steps={b.steps} />
        {b.notes && <p className="rounded-lg bg-paper p-3 text-sm text-slate-600">{b.notes}</p>}
        {b.final_status && <p className="text-sm">Final status: <b>{b.final_status}</b></p>}
      </header>

      <div role="tablist" aria-label="Board sections" className="flex gap-1 overflow-x-auto overflow-y-hidden border-b">
        {([['steps', `Steps (${b.steps.length})`], ['files', 'Files'], ['people', `People (${b.people.length})`], ['history', 'History']] as [Tab, string][]).map(([t, label]) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`-mb-px shrink-0 border-b-2 px-4 py-2 text-sm font-semibold ${tab === t ? 'border-gold text-ink' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
            {label}
          </button>
        ))}
      </div>

      {err && (
        <p role="alert" className="flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {err}<button onClick={() => setErr('')} className="text-xs underline">Close</button>
        </p>
      )}

      {tab === 'steps' && (
        <ol className="space-y-3">
          {b.steps.map((s) => <StepCard key={s.id} b={b} s={s} staff={staff} run={run} />)}
        </ol>
      )}

      {tab === 'files' && (
        <section className="space-y-2">
          <p className="text-sm text-slate-500">Everyone on the board can upload and ask to delete a file. The owner approves deletes.</p>
          <FileList ownerType="board" ownerId={b.code} canUpload={running} canDecide={b.can_decide_deletes} />
        </section>
      )}

      {tab === 'people' && <PeoplePanel b={b} staff={staff} run={run} />}

      {tab === 'history' && <BoardHistory code={b.code} version={b} />}

      {b.can_edit && running && (
        <section className="card flex flex-wrap items-center gap-2 p-4">
          <span className="text-sm font-semibold">Close this board:</span>
          {(['Delivered', 'Returned', 'Cancelled'] as const).map((f) => (
            <button key={f} onClick={() => confirm(`Mark ${b.code} as ${f}? This can't be undone.`) && run(`/boards/${b.code}/finish`, { method: 'POST', body: { final_status: f } }, `Board marked ${f}`)}
              className="btn-ghost py-1">{f}</button>
          ))}
        </section>
      )}
    </div>
  );
}

/** The steps side by side: done ✓, running (gold), still to come. Scrolls sideways on phones. */
function Timeline({ steps }: { steps: BoardStep[] }) {
  const done = steps.filter((s) => s.status === 'done').length;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{done} of {steps.length} steps done</span>
        <span>{Math.round((done / Math.max(1, steps.length)) * 100)}%</span>
      </div>
      <ol className="flex gap-2 overflow-x-auto pb-1">
        {steps.map((s) => (
          <li key={s.id} className="min-w-[8.5rem] flex-1">
            <div className={`h-1.5 rounded ${s.status === 'done' ? 'bg-emerald-500' : s.status === 'active' ? (s.used_pct >= 100 ? 'bg-red-600' : s.used_pct >= 85 ? 'bg-amber-500' : 'bg-gold') : 'bg-slate-200'}`} />
            <p className="mt-1.5 truncate text-sm font-semibold">
              <span className="text-slate-400">{s.position}.</span> {s.name} {s.status === 'done' && <span className="text-emerald-600">✓</span>}
            </p>
            <p className="text-xs text-slate-500">{fmtDay(s.planned_start)} → {fmtDay(s.planned_end)}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

type Run = (path: string, init: { method: string; body?: unknown }, done?: string) => Promise<boolean>;

function StepCard({ b, s, staff, run }: { b: Board; s: BoardStep; staff: Colleague[]; run: Run }) {
  const [editing, setEditing] = useState(false);
  const running = b.status === 'active';
  const canTick = running && s.status !== 'done';
  const canFinish = running && s.status === 'active' && (b.my_step_ids.includes(s.id) || b.can_edit);
  const ticked = s.checklist.filter((c) => c.done).length;
  const heads = s.members.filter((m) => m.is_head);

  return (
    <li className={`card space-y-3 p-4 ${s.status === 'active' ? 'border-gold ring-1 ring-gold/30' : ''}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${s.status === 'done' ? 'bg-emerald-100 text-emerald-800' : s.status === 'active' ? 'bg-gold text-ink' : 'bg-slate-100 text-slate-600'}`}>
          {s.status === 'done' ? '✓' : s.position}
        </span>
        <span className="text-base font-semibold">{s.name}</span>
        <Pill value={s.status === 'active' ? 'doing' : s.status === 'pending' ? 'todo' : 'done'} label={s.status === 'active' ? 'running' : s.status === 'pending' ? 'to come' : 'done'} />
        <span className="text-xs text-slate-500">{fmtDay(s.planned_start)} → {fmtDay(s.planned_end)}{s.percent ? ` · ${s.percent}% of the board's time` : s.days ? ` · ${s.days} working days` : ''}</span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex -space-x-1">{s.members.map((m) => <Avatar key={m.id} name={m.name} head={m.is_head} />)}</div>
        <p className="text-sm text-slate-600">
          {s.members.length === 0 ? 'Nobody yet' : s.members.map((m) => m.name).join(', ')}
          {heads.length > 0 && <span className="text-slate-400"> · head: {heads.map((h) => h.name).join(', ')}</span>}
        </p>
        {b.can_edit && running && s.status !== 'done' && !editing && (
          <button onClick={() => setEditing(true)} className="ml-auto text-xs font-semibold underline">Change people</button>
        )}
      </div>
      {editing && <StepPeopleEditor b={b} s={s} staff={staff} run={run} onClose={() => setEditing(false)} />}

      {s.status === 'active' && <UsedBar pct={s.used_pct} />}

      {s.checklist.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold text-slate-500">Checklist {ticked}/{s.checklist.length}</p>
          <ul className="space-y-1 text-sm">
            {s.checklist.map((c, i) => (
              <li key={i}>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={c.done} disabled={!canTick}
                    onChange={(e) => run(`/boards/${b.code}/steps/${s.id}/checklist`, { method: 'POST', body: { index: i, done: e.target.checked } })} />
                  <span className={c.done ? 'text-slate-400 line-through' : ''}>{c.text}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}
      {s.task_templates.length > 0 && <p className="text-xs text-slate-500">Tasks given when the step starts: {s.task_templates.join(' · ')}</p>}
      {canFinish && (
        <button onClick={() => confirm(`Mark "${s.name}" done and start the next step?`) && run(`/boards/${b.code}/steps/${s.id}/done`, { method: 'POST' }, `"${s.name}" done`)} className="btn-dark py-1">
          Mark step done
        </button>
      )}
    </li>
  );
}

/** Pick a step's people (at least one) and who heads it. Anyone picked is put on the board too. */
function StepPeopleEditor({ b, s, staff, run, onClose }: { b: Board; s: BoardStep; staff: Colleague[]; run: Run; onClose: () => void }) {
  const [picked, setPicked] = useState<Set<number>>(() => new Set(s.members.map((m) => m.id)));
  const [heads, setHeads] = useState<Set<number>>(() => new Set(s.members.filter((m) => m.is_head).map((m) => m.id)));
  const [q, setQ] = useState('');
  const onBoard = useMemo(() => new Set(b.people.map((p) => p.id)), [b.people]);
  // People on the board first, then everyone else; filtered by the search box
  const list = useMemo(() => [...staff].sort((x, y) => Number(onBoard.has(y.id)) - Number(onBoard.has(x.id)) || x.name.localeCompare(y.name))
    .filter((c) => c.name.toLowerCase().includes(q.trim().toLowerCase())), [staff, onBoard, q]);

  const toggle = (id: number) => {
    const p = new Set(picked), h = new Set(heads);
    if (p.has(id)) { p.delete(id); h.delete(id); } else p.add(id);
    setPicked(p);
    setHeads(h);
  };
  const toggleHead = (id: number) => {
    const h = new Set(heads);
    if (h.has(id)) h.delete(id); else h.add(id);
    setHeads(h);
  };
  async function save() {
    const ok = await run(`/boards/${b.code}/steps/${s.id}/people`, { method: 'PUT', body: { member_ids: [...picked], head_ids: [...heads] } }, `People on "${s.name}" saved`);
    if (ok) onClose();
  }

  return (
    <div className="space-y-2 rounded-lg border bg-paper p-3">
      <div className="flex flex-wrap items-center gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search staff" className="input max-w-xs py-1" aria-label="Search staff" />
        <span className="text-xs text-slate-500">Tick who works on this step; ★ makes them its head.</span>
      </div>
      <ul className="max-h-60 divide-y overflow-y-auto rounded-lg border bg-white">
        {list.map((c) => (
          <li key={c.id} className="flex items-center gap-2 px-3 py-1.5 text-sm">
            <label className="flex flex-1 items-center gap-2">
              <input type="checkbox" checked={picked.has(c.id)} onChange={() => toggle(c.id)} />
              {c.name}
              {!onBoard.has(c.id) && <span className="text-xs text-slate-400">(will be added to the board)</span>}
            </label>
            {picked.has(c.id) && (
              <button type="button" onClick={() => toggleHead(c.id)} aria-pressed={heads.has(c.id)}
                className={`rounded px-2 text-xs font-semibold ${heads.has(c.id) ? 'bg-gold text-ink' : 'text-slate-400 hover:text-gold-dark'}`}>
                ★ head
              </button>
            )}
          </li>
        ))}
        {list.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">No staff found.</li>}
      </ul>
      {picked.size === 0 && <p className="text-xs text-red-700">A step needs at least one person.</p>}
      <div className="flex gap-2">
        <button onClick={save} disabled={picked.size === 0} className="btn-dark py-1 disabled:opacity-50">Save</button>
        <button onClick={onClose} className="btn-ghost py-1">Cancel</button>
      </div>
    </div>
  );
}

function PeoplePanel({ b, staff, run }: { b: Board; staff: Colleague[]; run: Run }) {
  const [adding, setAdding] = useState('');
  const canEdit = b.can_edit && b.status === 'active';
  const onBoard = new Set(b.people.map((p) => p.id));
  const others = staff.filter((c) => !onBoard.has(c.id));
  const stepName = (pos: number) => b.steps.find((s) => s.position === pos)?.name ?? `Step ${pos}`;

  async function add() {
    if (!adding) return;
    if (await run(`/boards/${b.code}/people`, { method: 'POST', body: { user_id: Number(adding) } }, 'Added to the board')) setAdding('');
  }

  return (
    <section className="space-y-3">
      <p className="text-sm text-slate-500">
        Everyone here can see and update the board. {canEdit ? 'You can add or remove people.' : 'The owner adds and removes people.'}
      </p>
      {canEdit && (
        <div className="card flex flex-wrap items-center gap-2 p-3">
          <select value={adding} onChange={(e) => setAdding(e.target.value)} className="input max-w-xs py-1" aria-label="Person to add">
            <option value="">Add someone…</option>
            {others.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button onClick={add} disabled={!adding} className="btn-dark py-1 disabled:opacity-50">Add to board</button>
        </div>
      )}
      <ul className="card divide-y">
        {b.people.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-3 p-3">
            <Avatar name={p.name} />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{p.name} {p.is_owner && <Pill value="active" label="owner" />}</p>
              <p className="text-xs text-slate-500">{p.steps.length ? `Works on: ${p.steps.map(stepName).join(', ')}` : 'Not on a step (can still see and update the board)'}</p>
            </div>
            {canEdit && !p.is_owner && (
              <button onClick={() => confirm(`Remove ${p.name} from ${b.code}? Their files and history stay; their open tasks on this board are closed.`)
                && run(`/boards/${b.code}/people/${p.id}`, { method: 'DELETE' }, `${p.name} removed`)}
                className="text-xs text-red-700 underline">
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------- Board list ----------
const FILTERS = [['all', 'All'], ['on_track', 'On track'], ['at_risk', 'At risk'], ['late_board', 'Late']] as const;

export function BoardList({ base, boards }: { base: string; boards: BoardSummary[] }) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>('all');
  const [q, setQ] = useState('');
  const count = (f: string) => (f === 'all' ? boards.length : boards.filter((b) => b.state === f).length);
  const words = q.trim().toLowerCase();
  const shown = boards.filter((b) => (filter === 'all' || b.state === filter)
    && (!words || `${b.code} ${b.name} ${b.client}`.toLowerCase().includes(words)));

  if (boards.length === 0) return <p className="card p-6 text-sm text-slate-500">No order boards here.</p>;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map(([f, label]) => (
          <button key={f} onClick={() => setFilter(f)} aria-pressed={filter === f}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${filter === f ? 'border-ink bg-ink text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}>
            {label} ({count(f)})
          </button>
        ))}
        <label className="relative ml-auto w-full sm:w-64">
          <span className="pointer-events-none absolute left-2.5 top-2 text-slate-400"><Icon name="search" className="h-4 w-4" /></span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Code, order or client" aria-label="Search boards" className="input py-1.5 pl-8" />
        </label>
      </div>
      {shown.length === 0 && <p className="card p-6 text-sm text-slate-500">No boards match.</p>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {shown.map((b) => (
          <Link key={b.code} href={`${base}/${b.code}`} className="card card-lift space-y-3 p-4">
            <div className="flex items-center gap-2">
              <span className="font-bold">{b.code}</span>
              <BoardStatePill state={b.state} />
              <span className="ml-auto text-xs text-slate-500">Deadline {fmtDay(b.deadline)}</span>
            </div>
            <div>
              <p className="truncate font-semibold">{b.name}</p>
              <p className="truncate text-sm text-slate-500">{b.client}</p>
            </div>
            <div className="flex gap-1" aria-label={`${b.steps_done} of ${b.steps_total} steps done`}>
              {Array.from({ length: b.steps_total }, (_, i) => (
                <span key={i} className={`h-1.5 flex-1 rounded ${i < b.steps_done ? 'bg-emerald-500' : i === b.steps_done && b.status === 'active' ? 'bg-gold' : 'bg-slate-200'}`} />
              ))}
            </div>
            <p className="text-xs text-slate-500">
              {b.status === 'finished' ? `Finished${b.final_status ? `: ${b.final_status}` : ''}` : `Step ${Math.min(b.steps_done + 1, b.steps_total)} of ${b.steps_total}${b.current_step ? `: ${b.current_step}` : ''}`}
            </p>
            {b.current_used_pct !== null && <UsedBar pct={b.current_used_pct} />}
          </Link>
        ))}
      </div>
    </div>
  );
}
