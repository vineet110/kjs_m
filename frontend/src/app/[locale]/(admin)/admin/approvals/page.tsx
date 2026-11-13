'use client';
// Approvals inbox: everything waiting for a yes/no, in one place. Sections you can't approve are hidden.
// Sign-ups: waiting ones (Approve / Reject with a reason), then the approved list (Edit opens that person in
// Manage employees) and the rejected list (reason, who, when; an admin can still approve). Reloads itself
// when the portal's 30-second check sees the number waiting change.
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import ApproveCard, { type Perm, type StaffUser } from '@/components/portal/ApproveCard';
import { useMe } from '@/components/portal/PortalShell';
import { useToast } from '@/components/portal/Toast';
import { approvalsChanged } from '@/lib/portal-session';
import { EmptyState, fmtDay, fmtIST, PageTitle } from '@/components/portal/ui';
import { api, ApiFailure, type Regularization, type StoredFile } from '@/lib/api';
import { useOnUpdate } from '@/lib/updates';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

type Inbox = {
  signups: StaffUser[] | null; approved: StaffUser[] | null; rejected: StaffUser[] | null;
  regularizations: Regularization[] | null; file_deletes: StoredFile[] | null;
};
type SignupTab = 'waiting' | 'approved' | 'rejected';

export default function Approvals() {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [perms, setPerms] = useState<Perm[]>([]);
  const [err, setErr] = useState('');
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const [tab, setTab] = useState<SignupTab>('waiting');
  const toast = useToast();
  const me = useMe();

  const latest = useRef(0); // only the newest answer counts: an older one can't bring back a decided sign-up
  const load = useCallback(() => {
    const mine = ++latest.current;
    setLoadErr(null);
    // Both must load: approving a sign-up from an empty permissions list would give no permissions
    api<Inbox>('/admin/approvals').then(async (i) => {
      const p = i.signups !== null ? await api<Perm[]>('/admin/permissions') : null;
      if (mine !== latest.current) return;
      if (p) setPerms(p);
      setInbox(i);
    }).catch((e) => { if (mine === latest.current) setLoadErr(e); });
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  useOnUpdate(me.id, (u) => u.approvals, load); // something new is waiting (or someone else decided)

  // `done` = the toast shown when it worked ("Approved ✓")
  async function run(path: string, body: unknown, done: string) {
    setErr('');
    try {
      await api(path, { method: 'POST', body });
      toast(done);
      approvalsChanged();
      load();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
    }
  }

  if (loadErr) return <LoadError error={loadErr} onRetry={load} />;
  if (!inbox) return <Loading />;
  const count = (inbox.signups?.length ?? 0) + (inbox.regularizations?.length ?? 0) + (inbox.file_deletes?.length ?? 0);

  return (
    <div className="space-y-8">
      <PageTitle title="All approvals" sub={count ? `${count} waiting for you.` : 'Nothing is waiting. All clear.'} />
      {err && <p className="text-sm text-red-700">{err}</p>}

      {inbox.signups !== null && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="mr-2 text-lg font-bold">New staff</h2>
            {([['waiting', 'Waiting', inbox.signups.length], ['approved', 'Approved', inbox.approved?.length ?? 0],
               ['rejected', 'Rejected', inbox.rejected?.length ?? 0]] as [SignupTab, string, number][]).map(([t, label, n]) => (
              <button key={t} onClick={() => setTab(t)} aria-pressed={tab === t}
                className={`rounded-full px-3 py-1 text-sm ${tab === t ? 'bg-ink text-white' : 'bg-white ring-1 ring-slate-200'}`}>
                {label} ({n})
              </button>
            ))}
          </div>

          {tab === 'waiting' && (
            <>
              {inbox.signups.length === 0 && <EmptyState tone="done" title="No sign-ups waiting" text="New staff who sign up will show here for you to approve." />}
              {inbox.signups.map((u) => <ApproveCard key={u.id} user={u} perms={perms} onDone={load} />)}
            </>
          )}

          {tab === 'approved' && (
            <DecidedList rows={inbox.approved ?? []} empty="Nobody approved yet."
              action={(u) => <Link href={`/admin/users/${u.id}`} className="btn-ghost py-1">Edit</Link>} />
          )}

          {tab === 'rejected' && (
            me.role === 'admin'
              // An admin can still approve a rejected sign-up: the same card, with the reason shown
              ? (inbox.rejected ?? []).length === 0
                ? <EmptyState tone="done" title="No rejected sign-ups" text="Sign-ups you reject show here with the reason." />
                : (inbox.rejected ?? []).map((u) => <ApproveCard key={u.id} user={u} perms={perms} onDone={load} />)
              : <DecidedList rows={inbox.rejected ?? []} empty="No rejected sign-ups." />
          )}
        </section>
      )}

      {inbox.regularizations !== null && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold">Missed punches ({inbox.regularizations.length})</h2>
          {inbox.regularizations.length === 0 && <EmptyState tone="done" title="No missed punches to check" text="When someone forgets to check in or out, their request shows here." />}
          {inbox.regularizations.map((r) => (
            <div key={r.id} className="card flex flex-wrap items-center gap-3 p-4 text-sm">
              <span className="font-semibold">{r.user_name}</span>
              <span>{fmtDay(r.day, true)} · {r.check_in}–{r.check_out ?? '?'}</span>
              <span className="text-slate-500">“{r.reason}”</span>
              <span className="ml-auto flex gap-2">
                <button onClick={() => run(`/attendance/approvals/${r.id}`, { approve: true }, `Approved ${r.user_name}'s missed punch`)} className="btn-dark py-1">Approve</button>
                <button onClick={() => run(`/attendance/approvals/${r.id}`, { approve: false }, `Rejected ${r.user_name}'s request`)} className="btn-ghost py-1">Reject</button>
              </span>
            </div>
          ))}
        </section>
      )}

      {inbox.file_deletes !== null && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold">File delete requests ({inbox.file_deletes.length})</h2>
          {inbox.file_deletes.length === 0 && <EmptyState tone="done" title="No delete requests" text="Requests to delete a file for good show here." />}
          {inbox.file_deletes.map((f) => (
            <div key={f.id} className="card flex flex-wrap items-center gap-3 p-4 text-sm">
              <a href={`/api/v1/files/${f.id}/download`} className="font-semibold underline">{f.name}</a>
              <span className="text-slate-500">{f.owner_type} {f.owner_id} · asked by {f.requested_by_name} · uploaded {fmtIST(f.created_at)}</span>
              <span className="text-slate-500">“{f.delete_reason}”</span>
              <span className="ml-auto flex gap-2">
                <button onClick={() => confirm(`Delete ${f.name} for good?`) && run(`/files/${f.id}/delete-decision`, { approve: true }, `Deleted ${f.name}`)} className="btn-dark py-1">Delete</button>
                <button onClick={() => run(`/files/${f.id}/delete-decision`, { approve: false }, `Kept ${f.name}`)} className="btn-ghost py-1">Keep</button>
              </span>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

/** Approved or rejected sign-ups: who, decided by whom and when, the reason (rejected), and an action. */
function DecidedList({ rows, empty, action }: { rows: StaffUser[]; empty: string; action?: (u: StaffUser) => React.ReactNode }) {
  if (rows.length === 0) return <p className="card p-4 text-sm text-slate-500">{empty}</p>;
  return (
    <div className="card divide-y">
      {rows.map((u) => (
        <div key={u.id} className="flex flex-wrap items-center gap-3 p-3 text-sm">
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{u.name} <span className="font-normal text-slate-500">· {u.email}</span></p>
            <p className="text-xs text-slate-500">
              {u.decided_by_name ? `By ${u.decided_by_name}` : 'Decided'}{u.approved_at ? ` · ${fmtIST(u.approved_at)}` : ''}
              {u.job_title ? ` · ${u.job_title}` : ''}
            </p>
            {u.rejection_reason && <p className="mt-0.5 text-red-700">“{u.rejection_reason}”</p>}
          </div>
          {action?.(u)}
        </div>
      ))}
    </div>
  );
}
