'use client';
// Lead Management > Contacts > one contact. Opens on one enquiry (the lead in the address); the person's
// other enquiries are chips under the name. Same page for admin and staff.
// Left: the header, the lead pipeline (New → Contacted → Closed) and the tabs (Info, Notes, Task, Timeline,
// Proposals). Right: quick actions (Notes, Task, Lead Share).
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useMe } from '@/components/portal/PortalShell';
import { Icon, type IconName } from '@/components/portal/icons';
import { EmptyState, fmtIST, Msg, Pill } from '@/components/portal/ui';
import Loading from '@/components/ui/Loading';
import { api, ApiFailure, type Colleague, type ContactDetail, type Lead, type LeadNote, type Task } from '@/lib/api';

const SOURCE: Record<string, string> = {
  enquiry_form: 'Website enquiry', price_sheet: 'Price sheet', spec_pdf: 'Spec sheet', sample: 'Sample request',
  quote: 'Quote request', configurator: 'Private-label tool', koko: 'Koko chat', internal: 'Internal (added by staff)',
};
const OUTCOMES = ['quote_sent', 'sample_sent', 'order_won', 'not_interested', 'no_reply', 'spam'];
const STAGES = [
  { key: 'new', label: 'New', dot: 'bg-sky-500' },
  { key: 'contacted', label: 'Contacted', dot: 'bg-amber-500' },
  { key: 'closed', label: 'Closed', dot: 'bg-emerald-500' },
] as const;
type Tab = 'info' | 'notes' | 'task' | 'timeline' | 'proposals';
const TABS: { key: Tab; label: string; icon: IconName }[] = [
  { key: 'info', label: 'Info', icon: 'info' },
  { key: 'notes', label: 'Notes', icon: 'note' },
  { key: 'task', label: 'Task', icon: 'tasks' },
  { key: 'timeline', label: 'Timeline', icon: 'history' },
  { key: 'proposals', label: 'Proposals', icon: 'file' },
];

export default function ContactPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ContactDetail | null>(null);
  const [failed, setFailed] = useState('');
  const [tab, setTab] = useState<Tab>('info');
  const [sharing, setSharing] = useState(false);
  const [notes, setNotes] = useState<LeadNote[] | null>(null);

  const load = useCallback(() => {
    api<ContactDetail>(`/employee/contacts/${id}`)
      .then((d) => { setData(d); setFailed(''); })
      .catch((e) => setFailed(e instanceof ApiFailure && e.status === 404 ? 'This lead was not found, or it belongs to a colleague.' : 'Could not load this contact.'));
    api<LeadNote[]>(`/employee/leads/${id}/notes`).then(setNotes).catch(() => setNotes([]));
  }, [id]);
  useEffect(() => {
    load();
  }, [load]);

  if (failed) return <div className="space-y-4"><Back name="" /><EmptyState title="Can't open this contact" text={failed} /></div>;
  if (!data) return <Loading />;
  const lead = data.lead;

  return (
    <div className="space-y-4">
      <Back name={lead.name} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-4">
          <Header lead={lead} enquiries={data.enquiries} />
          <Pipeline lead={lead} onChange={load} />
          <div className="card">
            <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-slate-100 px-3 pt-2">
              {TABS.map((t) => (
                <button key={t.key} role="tab" aria-selected={tab === t.key} type="button" onClick={() => setTab(t.key)}
                  className={`flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-sm ${tab === t.key ? 'border-orange-500 font-semibold text-orange-600' : 'border-transparent text-slate-600 hover:text-slate-900'}`}>
                  <Icon name={t.icon} className="h-4 w-4" />{t.label}
                </button>
              ))}
            </div>
            <div className="p-4">
              {tab === 'info' && <Info lead={lead} />}
              {tab === 'notes' && <Notes lead={lead} notes={notes} onChange={load} />}
              {tab === 'task' && <Tasks lead={lead} />}
              {tab === 'timeline' && <Timeline lead={lead} notes={notes} />}
              {tab === 'proposals' && <EmptyState icon="file" title="No proposals yet" text="Quotes and proposals are not recorded in the portal yet. Log a sent quote as a note for now." />}
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="card p-4">
            <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Quick actions</h2>
            <div className="grid grid-cols-2 gap-2">
              <Quick icon="note" label="Notes" onClick={() => setTab('notes')} />
              <Quick icon="tasks" label="Task" onClick={() => setTab('task')} />
              <Quick icon="share" label="Lead Share" onClick={() => setSharing(!sharing)} wide />
            </div>
            {sharing && <Share lead={lead} onDone={() => { setSharing(false); load(); }} />}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Back({ name }: { name: string }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-lg font-semibold">
      <Link href="/employee/contacts" aria-label="Back to contacts" className="rounded p-1 text-slate-500 hover:bg-slate-100"><Icon name="arrow" className="h-5 w-5" /></Link>
      <span className="text-slate-300">|</span>
      <Link href="/employee/contacts" className="hover:underline">Contacts</Link>
      {name && <><span className="text-slate-400">›</span><span>{name}</span></>}
    </nav>
  );
}

function Header({ lead, enquiries }: { lead: Lead; enquiries: Lead[] }) {
  const [showPhone, setShowPhone] = useState(false);
  // The phone is hidden until asked for (the screen may be seen by others); the last 4 digits help recognise it
  const masked = lead.phone ? `${'*'.repeat(8)}${lead.phone.replace(/\D/g, '').slice(-4)}` : '';
  return (
    <div className="card flex flex-wrap items-start gap-4 p-4">
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-orange-50 text-xl font-bold text-orange-600">
        {lead.name.charAt(0).toUpperCase()}
      </span>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">{lead.name}</h1>
          <Pill value={lead.status} />
          {lead.company && <span className="text-sm text-slate-500">· {lead.company}</span>}
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          {lead.email && <a href={`mailto:${lead.email}`} className="rounded-full bg-slate-100 px-3 py-1 hover:bg-slate-200">{lead.email}</a>}
          {lead.phone && (
            showPhone ? <a href={`tel:${lead.phone.replace(/\s/g, '')}`} className="rounded-full bg-slate-100 px-3 py-1 hover:bg-slate-200">{lead.phone}</a>
              : <button type="button" onClick={() => setShowPhone(true)} title="Show the number" className="rounded-full bg-slate-100 px-3 py-1 hover:bg-slate-200">{masked}</button>
          )}
        </div>
        {enquiries.length > 1 && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-slate-500">{enquiries.length} enquiries:</span>
            {enquiries.map((e) => (
              <Link key={e.id} href={`/employee/contacts/${e.id}`} aria-current={e.id === lead.id ? 'page' : undefined}
                className={`rounded-full px-2.5 py-0.5 ring-1 ${e.id === lead.id ? 'bg-orange-50 font-semibold text-orange-700 ring-orange-200' : 'text-slate-600 ring-slate-200 hover:bg-slate-50'}`}>
                {e.product_name || e.category_name || SOURCE[e.source] || e.source} · {fmtIST(e.created_at)}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ago(iso: string) {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'}`;
  const h = Math.round(mins / 60);
  if (h < 48) return `${h} hour${h === 1 ? '' : 's'}`;
  return `${Math.round(h / 24)} days`;
}

function Pipeline({ lead, onChange }: { lead: Lead; onChange: () => void }) {
  const [closing, setClosing] = useState(false);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  async function move(status: string, outcome = '') {
    setBusy(true);
    setErr('');
    try {
      await api(`/employee/leads/${lead.id}`, { method: 'PATCH', body: { status, outcome } });
      setClosing(false);
      onChange();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not change the stage.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="card space-y-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">Lead Pipeline</h2>
          <p className="text-xs text-slate-500">Track movement across the sales funnel</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-slate-600">
          <span className="rounded-md border border-slate-200 px-2 py-1">Received {fmtIST(lead.created_at)}</span>
          <span className="rounded-md border border-slate-200 px-2 py-1">{ago(lead.created_at)} ago</span>
          {lead.sla_label && <Pill value={lead.sla_state === 'done' ? 'closed' : lead.sla_state} label={lead.sla_label} />}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {STAGES.map((s) => {
          const here = lead.status === s.key;
          return (
            <button key={s.key} type="button" disabled={busy || here}
              onClick={() => (s.key === 'closed' ? setClosing(true) : move(s.key))}
              aria-pressed={here}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm ${here ? 'bg-blue-600 font-semibold text-white' : 'bg-slate-50 text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100'}`}>
              <span className={`h-2 w-2 rounded-full ${here ? 'bg-white' : s.dot}`} />{s.label}
            </button>
          );
        })}
        {closing && (
          <select autoFocus disabled={busy} defaultValue="" onChange={(e) => e.target.value && move('closed', e.target.value)} className="input w-auto py-1 text-sm">
            <option value="">Close with outcome…</option>
            {OUTCOMES.map((o) => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
          </select>
        )}
      </div>
      {err && <p className="text-sm text-red-700">{err}</p>}
    </div>
  );
}

function Field({ icon, label, children }: { icon: IconName; label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-orange-50 text-orange-500"><Icon name={icon} className="h-4 w-4" /></span>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
        <p className="break-words text-sm text-slate-800">{children || '—'}</p>
      </div>
    </div>
  );
}

function Info({ lead }: { lead: Lead }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 rounded-lg border border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field icon="check" label="Lead status">{lead.status === 'closed' ? `Closed${lead.outcome ? ` (${lead.outcome.replace(/_/g, ' ')})` : ''}` : 'Active'}</Field>
        <Field icon="mail" label="Email">{lead.email}</Field>
        <Field icon="phone" label="Phone">{lead.phone}</Field>
        <Field icon="box" label="Product">{lead.product_name}</Field>
        <Field icon="globe" label="Source">{SOURCE[lead.source] ?? lead.source}</Field>
        <Field icon="layers" label="Category">{lead.category_name}</Field>
        <Field icon="user" label="Owner">{lead.owner_name ?? 'Unassigned'}</Field>
        <Field icon="user" label="Created by">{lead.created_by_name ?? (lead.source === 'internal' ? '' : 'Website visitor')}</Field>
        <Field icon="clock" label="Created at">{fmtIST(lead.created_at)}</Field>
        <Field icon="clock" label="Updated at">{lead.updated_at ? fmtIST(lead.updated_at) : ''}</Field>
        <Field icon="home" label="Company">{lead.company}</Field>
        <Field icon="globe" label="Country">{lead.country}</Field>
        <Field icon="users" label="Buyer type">{lead.buyer_type}</Field>
        <Field icon="box" label="Quantity">{lead.quantity}</Field>
      </div>
      {lead.message && (
        <div className="rounded-lg bg-slate-50 p-3 text-sm">
          <p className="mb-1 text-xs font-semibold uppercase text-slate-500">Message</p>
          <p className="whitespace-pre-wrap">{lead.message}</p>
        </div>
      )}
      {lead.chat_summary && (
        <div className="rounded-lg bg-slate-50 p-3 text-sm">
          <p className="mb-1 text-xs font-semibold uppercase text-slate-500">Koko chat summary</p>
          <p className="whitespace-pre-wrap">{lead.chat_summary}</p>
        </div>
      )}
    </div>
  );
}

function Notes({ lead, notes, onChange }: { lead: Lead; notes: LeadNote[] | null; onChange: () => void }) {
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => box.current?.focus(), []); // opened from the quick action: ready to type
  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    try {
      await api(`/employee/leads/${lead.id}/notes`, { method: 'POST', body: Object.fromEntries(new FormData(form)) });
      form.reset();
      setMsg(null);
      onChange();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save the note.' });
    }
  }
  const shown = (notes ?? []).filter((n) => ['note', 'call', 'email'].includes(n.kind)).reverse();
  return (
    <div className="space-y-4">
      <form onSubmit={add} className="space-y-2">
        <textarea ref={box} name="text" required maxLength={2000} rows={3} placeholder="What happened? e.g. Called, wants samples of 3-in-1" className="input" />
        <div className="flex items-center gap-2">
          {/* A call or email also counts as the first reply (stops the respond timer) */}
          <select name="kind" className="input w-auto py-1"><option value="note">Note</option><option value="call">Call</option><option value="email">Email</option></select>
          <button className="btn-dark py-1">Add note</button>
        </div>
        <Msg msg={msg} />
      </form>
      {notes === null ? <Loading /> : shown.length === 0 ? <p className="text-sm text-slate-500">No notes yet.</p> : (
        <ul className="space-y-2">
          {shown.map((n) => (
            <li key={n.id} className="rounded-lg border border-slate-100 p-3 text-sm">
              <p className="mb-1 text-xs text-slate-400">{fmtIST(n.created_at)} · {n.user_name} · {n.kind}</p>
              <p className="whitespace-pre-wrap">{n.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Tasks({ lead }: { lead: Lead }) {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = useCallback(() => {
    api<Task[]>(`/employee/leads/${lead.id}/tasks`).then(setTasks).catch(() => setTasks([]));
  }, [lead.id]);
  useEffect(() => {
    load();
  }, [load]);
  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    try {
      await api(`/employee/leads/${lead.id}/tasks`, { method: 'POST', body: { title: f.title, due_at: f.due ? new Date(`${f.due}:00+05:30`).toISOString() : null } }); // the box is IST, whatever the computer's zone
      form.reset();
      setMsg({ ok: true, text: 'Task added. It is also in your Tasks page.' });
      load();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not add the task.' });
    }
  }
  async function done(t: Task, yes: boolean) {
    await api(`/tasks/${t.id}`, { method: 'PATCH', body: { status: yes ? 'done' : 'todo' } }).catch(() => undefined);
    load();
  }
  return (
    <div className="space-y-4">
      <form onSubmit={add} className="grid gap-2 sm:grid-cols-[1fr_14rem_auto]">
        <input name="title" required minLength={2} maxLength={200} placeholder="e.g. Send the price sheet" className="input" aria-label="Task" />
        <input name="due" type="datetime-local" className="input" aria-label="Due (IST)" />
        <button className="btn-dark">Add task</button>
      </form>
      <Msg msg={msg} />
      {tasks === null ? <Loading /> : tasks.length === 0 ? <p className="text-sm text-slate-500">No tasks on this lead.</p> : (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100">
          {tasks.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-2 p-3 text-sm">
              <input type="checkbox" aria-label="Done" checked={t.status === 'done'} onChange={(e) => done(t, e.target.checked)} />
              <span className={t.status === 'done' ? 'text-slate-400 line-through' : 'font-medium'}>{t.title}</span>
              {t.overdue && <Pill value="overdue" />}
              <span className="ml-auto text-xs text-slate-500">{t.assignee_name} · {t.due_at ? `Due ${fmtIST(t.due_at)}` : 'No due date'}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Timeline({ lead, notes }: { lead: Lead; notes: LeadNote[] | null }) {
  const events = [
    { at: lead.created_at, title: `Lead received · ${SOURCE[lead.source] ?? lead.source}`, text: lead.created_by_name ? `Added by ${lead.created_by_name}` : '' },
    ...(lead.responded_at ? [{ at: lead.responded_at, title: 'First reply', text: '' }] : []),
    ...(lead.resolved_at ? [{ at: lead.resolved_at, title: 'Closed', text: lead.outcome.replace(/_/g, ' ') }] : []),
    ...(notes ?? []).map((n) => ({ at: n.created_at, title: `${n.kind === 'handover' ? 'Lead shared' : n.kind} · ${n.user_name}`, text: n.text })),
  ].sort((a, b) => b.at.localeCompare(a.at));
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-5">
      {events.map((e, i) => (
        <li key={i} className="relative">
          <span className="absolute -left-[26px] top-1 h-3 w-3 rounded-full border-2 border-white bg-orange-500" />
          <p className="text-sm font-medium capitalize">{e.title}</p>
          <p className="text-xs text-slate-400">{fmtIST(e.at)}</p>
          {e.text && <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{e.text}</p>}
        </li>
      ))}
    </ol>
  );
}

function Quick({ icon, label, onClick, wide }: { icon: IconName; label: string; onClick: () => void; wide?: boolean }) {
  return (
    <button type="button" onClick={onClick} className={`flex flex-col items-center gap-1 rounded-lg border border-slate-200 p-3 text-sm text-slate-700 hover:border-orange-300 hover:bg-orange-50 ${wide ? 'col-span-2' : ''}`}>
      <Icon name={icon} className="h-5 w-5 text-emerald-600" />{label}
    </button>
  );
}

/** Lead Share: hand the lead to a colleague (admins and leads.view_all: assign it to anyone). */
function Share({ lead, onDone }: { lead: Lead; onDone: () => void }) {
  const me = useMe();
  const all = me.permissions.includes('leads.view_all');
  const [staff, setStaff] = useState<Colleague[]>([]);
  const [err, setErr] = useState('');
  useEffect(() => {
    api<Colleague[]>('/employee/colleagues').then(setStaff).catch(() => setStaff([]));
  }, []);
  async function give(userId: string) {
    if (!userId) return;
    try {
      await api(all ? `/admin/leads/${lead.id}/assign` : `/employee/leads/${lead.id}/handover`, { method: 'POST', body: { user_id: Number(userId) } });
      onDone();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not share the lead.');
    }
  }
  return (
    <div className="mt-3 space-y-2">
      <label className="label" htmlFor="share-to">Share with</label>
      <select id="share-to" defaultValue="" onChange={(e) => give(e.target.value)} className="input">
        <option value="">Pick a colleague…</option>
        {staff.filter((c) => c.id !== lead.assigned_to).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      {err && <p className="text-sm text-red-700">{err}</p>}
    </div>
  );
}
