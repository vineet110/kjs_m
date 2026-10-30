'use client';
// My tasks: everything I need to do, from every source. Managers (tasks.assign) can give tasks
// and look at anyone's list.
import { useCallback, useEffect, useState } from 'react';
import { useMe } from '@/components/portal/PortalShell';
import { fmtIST, Msg, PageTitle, Pill } from '@/components/portal/ui';
import { api, ApiFailure, type Colleague, type Task } from '@/lib/api';
import Loading from '@/components/ui/Loading';

const SOURCES = ['own', 'manager', 'lead', 'board', 'batch'];

export default function TasksPage() {
  const me = useMe();
  const canAssign = me.permissions.includes('tasks.assign');
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [filter, setFilter] = useState({ status: '', source: '', due: '', who: '' });
  const [staff, setStaff] = useState<Colleague[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    const qs = new URLSearchParams(Object.entries(filter).filter(([k, v]) => v && k !== 'who'));
    if (filter.who) qs.set('assignee_id', filter.who);
    api<Task[]>(`/tasks?${qs}`).then(setTasks).catch(() => setTasks([]));
  }, [filter]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (canAssign) api<Colleague[]>('/employee/colleagues').then(setStaff);
  }, [canAssign]);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    try {
      await api('/tasks', {
        method: 'POST',
        body: {
          title: f.title, notes: f.notes ?? '',
          due_at: f.due ? new Date(f.due).toISOString() : null,
          assignee_id: f.assignee_id ? Number(f.assignee_id) : null,
        },
      });
      setMsg({ ok: true, text: 'Task added.' });
      form.reset();
      load();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save.' });
    }
  }

  const set = (k: keyof typeof filter) => (e: React.ChangeEvent<HTMLSelectElement>) => setFilter({ ...filter, [k]: e.target.value });

  return (
    <div className="space-y-6">
      <PageTitle title="Tasks" sub="Due times in IST." />
      <form onSubmit={add} className="card grid gap-3 p-4 md:grid-cols-4">
        <div className="md:col-span-2"><label className="label">Task</label><input name="title" required minLength={2} maxLength={200} className="input" placeholder="Send spec sheet to Al Noor" /></div>
        <div><label className="label">Due</label><input type="datetime-local" name="due" className="input" /></div>
        {canAssign ? (
          <div><label className="label">For</label>
            <select name="assignee_id" className="input"><option value="">Me</option>{staff.filter((c) => c.id !== me.id).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
          </div>
        ) : <div />}
        <div className="md:col-span-3"><label className="label">Notes</label><input name="notes" maxLength={4000} className="input" /></div>
        <div className="flex items-end"><button className="btn-dark w-full">Add task</button></div>
        <div className="md:col-span-4"><Msg msg={msg} /></div>
      </form>

      <div className="flex flex-wrap gap-2 text-sm">
        <select value={filter.status} onChange={set('status')} className="input w-auto py-1"><option value="">Any status</option><option value="todo">To do</option><option value="doing">Doing</option><option value="done">Done</option></select>
        <select value={filter.due} onChange={set('due')} className="input w-auto py-1"><option value="">Any due date</option><option value="today">Due today</option><option value="overdue">Overdue</option></select>
        <select value={filter.source} onChange={set('source')} className="input w-auto py-1"><option value="">Any source</option>{SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
        {canAssign && (
          <select value={filter.who} onChange={set('who')} className="input w-auto py-1">
            <option value="">My tasks</option><option value="0">Everyone</option>
            {staff.filter((c) => c.id !== me.id).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
      </div>

      <div className="space-y-2">
        {tasks === null && <Loading />}
        {tasks?.length === 0 && <p className="card p-6 text-sm text-slate-500">No tasks here.</p>}
        {tasks?.map((t) => <TaskRow key={t.id} task={t} showOwner={filter.who !== ''} onChange={load} />)}
      </div>
    </div>
  );
}

function TaskRow({ task, showOwner, onChange }: { task: Task; showOwner: boolean; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState(task.notes);
  const [outcome, setOutcome] = useState(task.outcome);

  async function patch(body: Partial<Task>) {
    await api(`/tasks/${task.id}`, { method: 'PATCH', body });
    onChange();
  }

  return (
    <div className={`card p-3 ${task.overdue ? 'border-red-300' : ''}`}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <input type="checkbox" aria-label="Done" checked={task.status === 'done'} onChange={(e) => patch({ status: e.target.checked ? 'done' : 'todo' })} />
        <span className={`font-medium ${task.status === 'done' ? 'text-slate-400 line-through' : ''}`}>{task.title}</span>
        <Pill value={task.status} label={task.status === 'todo' ? 'to do' : task.status} />
        {task.overdue && <Pill value="overdue" />}
        <span className="text-xs text-slate-500">{task.source}{task.created_by_name && task.source === 'manager' ? ` · from ${task.created_by_name}` : ''}{showOwner ? ` · ${task.assignee_name}` : ''}</span>
        <span className="ml-auto text-xs text-slate-500">{task.due_at ? `Due ${fmtIST(task.due_at)}` : 'No due date'}</span>
        <button onClick={() => setOpen(!open)} className="text-xs underline">{open ? 'Close' : 'Details'}</button>
      </div>
      {open && (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <div><label className="label">Notes</label><textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className="input" /></div>
          <div><label className="label">Outcome</label><textarea value={outcome} onChange={(e) => setOutcome(e.target.value)} rows={3} className="input" placeholder="What came of it?" /></div>
          <div className="flex gap-2 md:col-span-2">
            <button onClick={() => patch({ notes, outcome })} className="btn-dark py-1">Save</button>
            {task.status === 'todo' && <button onClick={() => patch({ status: 'doing' })} className="btn-ghost py-1">Start</button>}
          </div>
        </div>
      )}
    </div>
  );
}
