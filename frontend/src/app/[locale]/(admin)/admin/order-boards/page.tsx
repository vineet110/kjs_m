'use client';
// Order boards (admin): every board with its state, and the "new board" form with a live plan preview.
import { useCallback, useEffect, useState } from 'react';
import { BoardList } from '@/components/portal/BoardDetail';
import { fmtDay, Msg, PageTitle, todayIST } from '@/components/portal/ui';
import { api, ApiFailure, type BoardSummary, type Colleague } from '@/lib/api';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

type StepDraft = { name: string; size: number; member_ids: number[]; head_ids: number[]; tasks: string; checklist: string };
const NEW_STEP: StepDraft = { name: '', size: 0, member_ids: [], head_ids: [], tasks: '', checklist: '' };

export default function AdminBoards() {
  const [boards, setBoards] = useState<BoardSummary[] | null>(null);
  const [showFinished, setShowFinished] = useState(false);
  const [creating, setCreating] = useState(false);
  const [loadErr, setLoadErr] = useState<unknown>(null);

  const load = useCallback(() => {
    setLoadErr(null);
    api<BoardSummary[]>(`/boards?include_finished=${showFinished}`).then(setBoards).catch(setLoadErr);
  }, [showFinished]);
  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <PageTitle title="All order boards" sub="Steps are planned on working days (Mon–Sat minus holidays). Alerts at 50, 85 and 100% of a step's time. You own the boards you create.">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showFinished} onChange={(e) => setShowFinished(e.target.checked)} /> Show finished</label>
          <button onClick={() => setCreating(!creating)} className="btn-dark">{creating ? 'Close form' : 'New board'}</button>
        </div>
      </PageTitle>
      {creating && <NewBoard onDone={() => { setCreating(false); load(); }} />}
      {loadErr ? <LoadError error={loadErr} onRetry={load} /> : boards === null ? <Loading /> : <BoardList base="/admin/order-boards" boards={boards} />}
    </div>
  );
}

function NewBoard({ onDone }: { onDone: () => void }) {
  const [staff, setStaff] = useState<Colleague[]>([]);
  const [head, setHead] = useState({ code: '', name: '', client: '', priority: 'medium', start: todayIST(), deadline: '', split_mode: 'percent', notes: '' });
  const [steps, setSteps] = useState<StepDraft[]>([
    { ...NEW_STEP, name: 'Sourcing', size: 30 }, { ...NEW_STEP, name: 'Production', size: 50 }, { ...NEW_STEP, name: 'Dispatch', size: 20 },
  ]);
  const [preview, setPreview] = useState<{ steps: { start: string; end: string }[]; plan_late: boolean } | null>(null);
  const [previewErr, setPreviewErr] = useState('');
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [staffErr, setStaffErr] = useState<unknown>(null);

  const loadStaff = useCallback(() => {
    setStaffErr(null);
    api<Colleague[]>('/employee/colleagues').then(setStaff).catch(setStaffErr);
  }, []);
  useEffect(() => {
    loadStaff();
  }, [loadStaff]);

  // Live plan preview whenever dates or sizes change.
  const sizes = steps.map((s) => s.size).join(',');
  useEffect(() => {
    if (!head.start || !head.deadline || steps.some((s) => !s.size)) return setPreview(null);
    const t = setTimeout(() => {
      api<{ steps: { start: string; end: string }[]; plan_late: boolean }>('/boards/preview', {
        method: 'POST', safeToRepeat: true, body: { start: head.start, deadline: head.deadline, split_mode: head.split_mode, sizes: steps.map((s) => s.size) },
      }).then((p) => { setPreview(p); setPreviewErr(''); })
        .catch((e) => { setPreview(null); setPreviewErr(e instanceof ApiFailure ? e.message : ''); });
    }, 300);
    return () => clearTimeout(t);
  }, [head.start, head.deadline, head.split_mode, sizes, steps]);

  const setStep = (i: number, patch: Partial<StepDraft>) => setSteps(steps.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const lines = (t: string) => t.split('\n').map((x) => x.trim()).filter(Boolean);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    const empty = steps.find((s) => s.member_ids.length === 0);
    if (empty) return setMsg({ ok: false, text: `Step "${empty.name || 'unnamed'}" needs at least one person.` });
    try {
      await api('/boards', {
        method: 'POST',
        body: {
          ...head,
          steps: steps.map((s) => ({
            name: s.name, member_ids: s.member_ids, head_ids: s.head_ids.filter((h) => s.member_ids.includes(h)), task_templates: lines(s.tasks), checklist: lines(s.checklist),
            ...(head.split_mode === 'percent' ? { percent: s.size } : { days: s.size }),
          })),
        },
      });
      onDone();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save.' });
    }
  }

  const total = steps.reduce((a, s) => a + (s.size || 0), 0);
  const h = (k: keyof typeof head) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setHead({ ...head, [k]: e.target.value });

  return (
    <form onSubmit={save} className="card space-y-4 p-5">
      {staffErr != null && <LoadError error={staffErr} onRetry={loadStaff} />}
      <div className="grid gap-3 md:grid-cols-4">
        <div><label className="label">Board code</label><input value={head.code} onChange={h('code')} required placeholder="ABC117-3" className="input uppercase" /></div>
        <div className="md:col-span-2"><label className="label">Order name</label><input value={head.name} onChange={h('name')} required minLength={2} placeholder="3-in-1 coffee sticks, 18 g" className="input" /></div>
        <div><label className="label">Client</label><input value={head.client} onChange={h('client')} required minLength={2} className="input" /></div>
        <div><label className="label">Start</label><input type="date" value={head.start} onChange={h('start')} required className="input" /></div>
        <div><label className="label">Deadline</label><input type="date" value={head.deadline} onChange={h('deadline')} required className="input" /></div>
        <div><label className="label">Priority</label><select value={head.priority} onChange={h('priority')} className="input"><option>low</option><option>medium</option><option>high</option></select></div>
        <div><label className="label">Split steps by</label><select value={head.split_mode} onChange={h('split_mode')} className="input"><option value="percent">% of the time</option><option value="days">fixed working days</option></select></div>
        <div className="md:col-span-4"><label className="label">Notes</label><textarea value={head.notes} onChange={h('notes')} rows={2} className="input" /></div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Steps {head.split_mode === 'percent' && <span className={`text-sm ${total === 100 ? 'text-emerald-700' : 'text-red-700'}`}>({total}% of 100%)</span>}</h3>
          <button type="button" onClick={() => setSteps([...steps, { ...NEW_STEP }])} className="btn-ghost py-1">Add step</button>
        </div>
        {steps.map((s, i) => (
          <div key={i} className="grid gap-2 rounded-lg border p-3 md:grid-cols-12">
            <div className="md:col-span-3"><label className="label">Step {i + 1}</label><input value={s.name} onChange={(e) => setStep(i, { name: e.target.value })} required minLength={2} className="input" /></div>
            <div className="md:col-span-2"><label className="label">{head.split_mode === 'percent' ? '% of time' : 'Working days'}</label><input type="number" min={1} value={s.size || ''} onChange={(e) => setStep(i, { size: Number(e.target.value) })} required className="input" /></div>
            <div className="md:col-span-3">
              <label className="label">People (★ = head)</label>
              <ul className="h-28 divide-y overflow-y-auto rounded-lg border bg-white text-sm" aria-label={`People on step ${i + 1}`}>
                {staff.map((c) => {
                  const on = s.member_ids.includes(c.id), head = s.head_ids.includes(c.id);
                  return (
                    <li key={c.id} className="flex items-center gap-2 px-2 py-1">
                      <label className="flex flex-1 items-center gap-2">
                        <input type="checkbox" checked={on} onChange={() => setStep(i, on
                          ? { member_ids: s.member_ids.filter((m) => m !== c.id), head_ids: s.head_ids.filter((h) => h !== c.id) }
                          : { member_ids: [...s.member_ids, c.id] })} />
                        {c.name}
                      </label>
                      {on && (
                        <button type="button" aria-pressed={head} title="Head of this step"
                          onClick={() => setStep(i, { head_ids: head ? s.head_ids.filter((h) => h !== c.id) : [...s.head_ids, c.id] })}
                          className={`rounded px-1.5 text-xs font-semibold ${head ? 'bg-gold text-ink' : 'text-slate-400 hover:text-gold-dark'}`}>★</button>
                      )}
                    </li>
                  );
                })}
              </ul>
              {s.member_ids.length === 0 && <p className="mt-1 text-xs text-amber-700">Pick at least one person.</p>}
            </div>
            <div className="md:col-span-2"><label className="label">Tasks (one per line)</label><textarea value={s.tasks} onChange={(e) => setStep(i, { tasks: e.target.value })} rows={3} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Checklist (one per line)</label><textarea value={s.checklist} onChange={(e) => setStep(i, { checklist: e.target.value })} rows={3} className="input" /></div>
            <div className="flex items-center justify-between text-xs text-slate-500 md:col-span-12">
              <span>{preview?.steps[i] ? `Planned ${fmtDay(preview.steps[i].start)} → ${fmtDay(preview.steps[i].end)}` : ''}</span>
              {steps.length > 1 && <button type="button" onClick={() => setSteps(steps.filter((_, j) => j !== i))} className="text-red-700 underline">Remove step</button>}
            </div>
          </div>
        ))}
        {previewErr && <p className="text-sm text-red-700">{previewErr}</p>}
        {preview?.plan_late && <p className="text-sm text-amber-700">These steps need more working days than the deadline allows. The plan will run past the deadline.</p>}
      </div>
      <Msg msg={msg} />
      <button className="btn-dark">Create board</button>
    </form>
  );
}
