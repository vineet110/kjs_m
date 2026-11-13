'use client';
// Approve a new staff sign-up and choose what they may do (per-person permissions, backlog D5), or reject it
// with a reason (required: the person may ask why). A rejected sign-up shows here again for an admin, who
// can still approve it later.
import { useState } from 'react';
import { api, ApiFailure } from '@/lib/api';
import { approvalsChanged } from '@/lib/portal-session';
import { useToast } from './Toast';

export type StaffUser = {
  id: number; name: string; email: string; phone: string | null; role: string; status: string; permissions: string[];
  created_at: string; employee_code?: string; branch?: string; job_title?: string; reporting_to?: number | null;
  approved_by?: number | null; approved_at?: string | null; rejection_reason?: string | null; decided_by_name?: string;
};
export type Perm = { key: string; label: string };

export default function ApproveCard({ user, perms, onDone }: { user: StaffUser; perms: Perm[]; onDone: () => void }) {
  const [chosen, setChosen] = useState<string[]>(['leads.view']);
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');
  const toast = useToast();
  const rejected = user.status === 'rejected';

  async function decide(path: string, body: unknown, done: string) {
    setBusy(true);
    try {
      await api(`/admin/users/${user.id}/${path}`, { method: 'POST', body });
      toast(done);
      approvalsChanged();
      onDone();
    } catch (e) {
      toast(e instanceof ApiFailure ? e.message : 'Could not save. Please try again.', 'error');
      setBusy(false); // the buttons work again (before, a failure left them stuck)
    }
  }

  return (
    <div className="card space-y-3 p-4">
      <div>
        <p className="font-semibold">{user.name}</p>
        <p className="text-sm text-slate-500">{user.email}{user.phone ? ` · ${user.phone}` : ''} · signed up {new Date(user.created_at).toLocaleDateString('en-IN')}</p>
        {rejected && user.rejection_reason && (
          <p className="mt-1 text-sm text-red-700">Rejected{user.decided_by_name ? ` by ${user.decided_by_name}` : ''}: “{user.rejection_reason}”</p>
        )}
      </div>
      <div>
        <p className="mb-1 text-xs font-semibold uppercase text-slate-500">What can {user.name.split(' ')[0]} do?</p>
        <div className="grid gap-1 sm:grid-cols-2">
          {perms.map((p) => (
            <label key={p.key} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={chosen.includes(p.key)}
                disabled={p.key === 'leads.view'}
                onChange={(e) => setChosen((c) => (e.target.checked ? [...c, p.key] : c.filter((k) => k !== p.key)))}
              />
              {p.label}
            </label>
          ))}
        </div>
      </div>
      {rejecting && (
        <div>
          <label className="label" htmlFor={`reject-${user.id}`}>Why are you rejecting {user.name.split(' ')[0]}? (required)</label>
          <textarea id={`reject-${user.id}`} value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={500}
            className="input" placeholder="e.g. Not a KJS employee" autoFocus />
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {!rejecting && (
          <button disabled={busy} onClick={() => decide('approve', { permissions: chosen }, `${user.name} is approved and can log in now`)} className="btn-dark">
            Approve
          </button>
        )}
        {!rejected && !rejecting && <button disabled={busy} onClick={() => setRejecting(true)} className="btn-ghost text-red-700">Reject</button>}
        {rejecting && (
          <>
            <button disabled={busy || reason.trim().length < 3} onClick={() => decide('reject', { reason: reason.trim() }, `${user.name}'s sign-up was rejected`)}
              className="btn-dark bg-red-700 hover:bg-red-800 disabled:opacity-50">
              Reject sign-up
            </button>
            <button disabled={busy} onClick={() => { setRejecting(false); setReason(''); }} className="btn-ghost">Cancel</button>
          </>
        )}
      </div>
    </div>
  );
}
