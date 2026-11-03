'use client';
// Approvals inbox: everything waiting for a yes/no, in one place. Sections you can't approve are hidden.
import { useCallback, useEffect, useState } from 'react';
import ApproveCard, { type Perm, type StaffUser } from '@/components/portal/ApproveCard';
import { useToast } from '@/components/portal/Toast';
import { EmptyState, fmtDay, fmtIST, PageTitle } from '@/components/portal/ui';
import { api, ApiFailure, type Regularization, type StoredFile } from '@/lib/api';
import Loading from '@/components/ui/Loading';

type Inbox = { signups: StaffUser[] | null; regularizations: Regularization[] | null; file_deletes: StoredFile[] | null };

export default function Approvals() {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [perms, setPerms] = useState<Perm[]>([]);
  const [err, setErr] = useState('');
  const toast = useToast();

  const load = useCallback(() => {
    api<Inbox>('/admin/approvals').then((i) => {
      setInbox(i);
      if (i.signups !== null) api<Perm[]>('/admin/permissions').then(setPerms);
    });
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  // `done` = the toast shown when it worked ("Approved ✓")
  async function run(path: string, body: unknown, done: string) {
    setErr('');
    try {
      await api(path, { method: 'POST', body });
      toast(done);
      load();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
    }
  }

  if (!inbox) return <Loading />;
  const count = (inbox.signups?.length ?? 0) + (inbox.regularizations?.length ?? 0) + (inbox.file_deletes?.length ?? 0);

  return (
    <div className="space-y-8">
      <PageTitle title="Approvals" sub={count ? `${count} waiting for you.` : 'Nothing is waiting. All clear.'} />
      {err && <p className="text-sm text-red-700">{err}</p>}

      {inbox.signups !== null && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold">New staff ({inbox.signups.length})</h2>
          {inbox.signups.length === 0 && <EmptyState tone="done" title="No sign-ups waiting" text="New staff who sign up will show here for you to approve." />}
          {inbox.signups.map((u) => <ApproveCard key={u.id} user={u} perms={perms} onDone={load} />)}
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
