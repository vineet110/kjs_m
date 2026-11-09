'use client';
// Edit a board's plan (order boards PR 4): start, deadline, how time is split, and the steps (rename,
// resize, add, remove, reorder), saved together. Dates for every step are worked out again; a live
// preview shows them before saving. Running and done steps stay first and can't be removed; only steps
// that haven't started can be moved or removed. Anyone on the board while unlocked; the owner when locked.
import { useEffect, useMemo, useState } from 'react';
import { api, ApiFailure, type Board, type Colleague } from '@/lib/api';
import { fmtDay, Pill } from './ui';

type Draft = {
  key: string; id: number | null; name: string; size: number; status: 'pending' | 'active' | 'done';
  member_ids: number[]; head_ids: number[]; tasks: string; checklist: string; // the last four: new steps only
};
type Preview = { steps: { start: string; end: string }[]; plan_late: boolean };

const lines = (t: string) => t.split('\n').map((x) => x.trim()).filter(Boolean);

export default function PlanEditor({ b, staff, onSave, onClose }: {
  b: Board; staff: Colleague[];
  onSave: (body: unknown) => Promise<boolean>; // PUT /boards/{code}/plan; true when saved
  onClose: () => void;
}) {
  const [start, setStart] = useState(b.start);
  const [deadline, setDeadline] = useState(b.deadline);
  const [mode, setMode] = useState(b.split_mode as 'percent' | 'days');
  const [steps, setSteps] = useState<Draft[]>(() => b.steps.map((s) => ({
    key: `s${s.id}`, id: s.id, name: s.name, size: (b.split_mode === 'percent' ? s.percent : s.days) ?? 1, status: s.status,
    member_ids: [], head_ids: [], tasks: '', checklist: '',
  })));
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewErr, setPreviewErr] = useState('');
  const [saving, setSaving] = useState(false);
  const [newKey, setNewKey] = useState(0);
  const [version] = useState(b.plan_version); // the plan this draft started from (b itself may refresh)
  // Only the owner brings new people onto the board; others pick from the people already on it
  const choices = useMemo(() => (b.can_edit ? staff : staff.filter((c) => b.people.some((p) => p.id === c.id))), [b, staff]);

  const started = steps.filter((s) => s.status !== 'pending').length; // they stay first
  const total = steps.reduce((a, s) => a + (s.size || 0), 0);
  const removed = b.steps.filter((s) => !steps.some((d) => d.id === s.id));

  // Live dates whenever dates, split or sizes change
  const sizes = steps.map((s) => s.size).join(',');
  useEffect(() => {
    setPreviewErr('');
    if (!start || !deadline || steps.some((s) => !s.size)) return setPreview(null);
    let stale = false; // an answer for inputs that have changed since is ignored (it may arrive late)
    const t = setTimeout(() => {
      api<Preview>('/boards/preview', { method: 'POST', safeToRepeat: true, body: { start, deadline, split_mode: mode, sizes: steps.map((s) => s.size) } }) // only works out dates
        .then((p) => { if (!stale) setPreview(p); })
        .catch((e) => { if (!stale) { setPreview(null); setPreviewErr(e instanceof ApiFailure ? e.message : ''); } });
    }, 300);
    return () => { stale = true; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `sizes` stands for the step sizes
  }, [start, deadline, mode, sizes]);

  const set = (key: string, patch: Partial<Draft>) => setSteps(steps.map((s) => (s.key === key ? { ...s, ...patch } : s)));
  const move = (i: number, by: -1 | 1) => {
    const j = i + by;
    if (j < started || j >= steps.length) return; // never above a running or done step
    const next = [...steps];
    [next[i], next[j]] = [next[j], next[i]];
    setSteps(next);
  };
  const add = () => {
    setSteps([...steps, { key: `n${newKey}`, id: null, name: '', size: 0, status: 'pending', member_ids: [], head_ids: [], tasks: '', checklist: '' }]);
    setNewKey(newKey + 1);
  };

  const missingPeople = steps.find((s) => s.id === null && s.member_ids.length === 0);
  async function save() {
    if (missingPeople) return;
    if (removed.length && !confirm(`Remove ${removed.map((s) => `"${s.name}"`).join(', ')}? Its checklist is deleted (History keeps a copy).`)) return;
    setSaving(true);
    const ok = await onSave({
      start, deadline, split_mode: mode, version,
      steps: steps.map((s) => (s.id !== null
        ? { id: s.id, name: s.name.trim(), size: s.size }
        : { name: s.name.trim(), size: s.size, member_ids: s.member_ids, head_ids: s.head_ids.filter((h) => s.member_ids.includes(h)),
            task_templates: lines(s.tasks), checklist: lines(s.checklist) })),
    });
    setSaving(false);
    if (ok) onClose();
  }

  return (
    <section className="card space-y-4 border-gold p-4" aria-label="Edit the plan">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-bold">Edit the plan</h2>
        <p className="text-xs text-slate-500">Running and done steps stay first. Only steps that haven&apos;t started can be moved or removed.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div><label className="label" htmlFor="plan-start">Start</label><input id="plan-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="input" /></div>
        <div><label className="label" htmlFor="plan-deadline">Deadline</label><input id="plan-deadline" type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="input" /></div>
        <div>
          <label className="label" htmlFor="plan-mode">Split steps by</label>
          <select id="plan-mode" value={mode} onChange={(e) => setMode(e.target.value as 'percent' | 'days')} className="input">
            <option value="percent">% of the time</option><option value="days">fixed working days</option>
          </select>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Steps {mode === 'percent' && <span className={`text-sm ${total === 100 ? 'text-emerald-700' : 'text-red-700'}`}>({total}% of 100%)</span>}</h3>
          <button type="button" onClick={add} className="btn-ghost py-1">Add step</button>
        </div>
        <ol className="space-y-2">
          {steps.map((s, i) => {
            const fixed = s.status !== 'pending';
            return (
              <li key={s.key} className={`space-y-2 rounded-lg border p-3 ${s.id === null ? 'border-dashed border-gold bg-paper' : 'bg-white'}`}>
                <div className="flex flex-wrap items-end gap-2">
                  <span className="w-6 pb-2 text-sm font-bold text-slate-400">{i + 1}.</span>
                  <div className="min-w-[10rem] flex-1">
                    <label className="label" htmlFor={`name-${s.key}`}>Step name</label>
                    <input id={`name-${s.key}`} value={s.name} onChange={(e) => set(s.key, { name: e.target.value })} minLength={2} required className="input" />
                  </div>
                  <div className="w-28">
                    <label className="label" htmlFor={`size-${s.key}`}>{mode === 'percent' ? '% of time' : 'Working days'}</label>
                    <input id={`size-${s.key}`} type="number" min={1} max={mode === 'percent' ? 100 : 365} value={s.size || ''} onChange={(e) => set(s.key, { size: Number(e.target.value) })} className="input" />
                  </div>
                  <div className="pb-2">{fixed ? <Pill value={s.status === 'active' ? 'doing' : 'done'} label={s.status === 'active' ? 'running' : 'done'} /> : s.id === null ? <Pill value="new" label="new" /> : <Pill value="todo" label="to come" />}</div>
                  {!fixed && (
                    <div className="flex gap-1 pb-1">
                      <button type="button" onClick={() => move(i, -1)} disabled={i <= started} aria-label={`Move ${s.name || 'step'} up`} className="btn-ghost px-2 py-1 disabled:opacity-30">↑</button>
                      <button type="button" onClick={() => move(i, 1)} disabled={i === steps.length - 1} aria-label={`Move ${s.name || 'step'} down`} className="btn-ghost px-2 py-1 disabled:opacity-30">↓</button>
                      <button type="button" onClick={() => setSteps(steps.filter((x) => x.key !== s.key))} className="px-2 text-xs text-red-700 underline">Remove</button>
                    </div>
                  )}
                </div>
                <p className="pl-8 text-xs text-slate-500">
                  {preview?.steps[i] ? `Planned ${fmtDay(preview.steps[i].start)} → ${fmtDay(preview.steps[i].end)}` : ' '}
                </p>
                {s.id === null && <NewStepFields s={s} staff={choices} set={(p) => set(s.key, p)} />}
              </li>
            );
          })}
        </ol>
        {removed.length > 0 && <p className="text-xs text-red-700">Will be removed: {removed.map((s) => s.name).join(', ')}.</p>}
        {previewErr && <p className="text-sm text-red-700">{previewErr}</p>}
        {preview?.plan_late && <p className="text-sm text-amber-700">These steps need more working days than the deadline allows. The plan will run past the deadline.</p>}
        {missingPeople && <p className="text-sm text-amber-700">Every new step needs at least one person.</p>}
      </div>

      <div className="flex gap-2">
        <button onClick={save} disabled={saving || !!missingPeople} className="btn-dark disabled:opacity-50">{saving ? 'Saving…' : 'Save plan'}</button>
        <button onClick={onClose} className="btn-ghost">Cancel</button>
      </div>
    </section>
  );
}

/** People (★ = head), tasks and checklist for a step being added. */
function NewStepFields({ s, staff, set }: { s: Draft; staff: Colleague[]; set: (p: Partial<Draft>) => void }) {
  const [q, setQ] = useState('');
  const list = useMemo(() => staff.filter((c) => c.name.toLowerCase().includes(q.trim().toLowerCase())), [staff, q]);
  return (
    <div className="grid gap-2 pl-8 md:grid-cols-3">
      <div>
        <label className="label" htmlFor={`find-${s.key}`}>People (★ = head)</label>
        <input id={`find-${s.key}`} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search staff" className="input mb-1 py-1" />
        <ul className="h-28 divide-y overflow-y-auto rounded-lg border bg-white text-sm">
          {list.map((c) => {
            const on = s.member_ids.includes(c.id), head = s.head_ids.includes(c.id);
            return (
              <li key={c.id} className="flex items-center gap-2 px-2 py-1">
                <label className="flex flex-1 items-center gap-2">
                  <input type="checkbox" checked={on} onChange={() => set(on
                    ? { member_ids: s.member_ids.filter((m) => m !== c.id), head_ids: s.head_ids.filter((h) => h !== c.id) }
                    : { member_ids: [...s.member_ids, c.id] })} />
                  {c.name}
                </label>
                {on && (
                  <button type="button" aria-pressed={head} title="Head of this step"
                    onClick={() => set({ head_ids: head ? s.head_ids.filter((h) => h !== c.id) : [...s.head_ids, c.id] })}
                    className={`rounded px-1.5 text-xs font-semibold ${head ? 'bg-gold text-ink' : 'text-slate-400 hover:text-gold-dark'}`}>★</button>
                )}
              </li>
            );
          })}
        </ul>
      </div>
      <div><label className="label" htmlFor={`tasks-${s.key}`}>Tasks (one per line)</label><textarea id={`tasks-${s.key}`} value={s.tasks} onChange={(e) => set({ tasks: e.target.value })} rows={4} className="input" /></div>
      <div><label className="label" htmlFor={`check-${s.key}`}>Checklist (one per line)</label><textarea id={`check-${s.key}`} value={s.checklist} onChange={(e) => set({ checklist: e.target.value })} rows={4} className="input" /></div>
    </div>
  );
}
