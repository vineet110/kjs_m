'use client';
// Approve a new staff sign-up and choose what they may do (per-person permissions, backlog D5).
import { useState } from 'react';
import { api } from '@/lib/api';

export type StaffUser = { id: number; name: string; email: string; phone: string | null; role: string; status: string; permissions: string[]; created_at: string };
export type Perm = { key: string; label: string };

export default function ApproveCard({ user, perms, onDone }: { user: StaffUser; perms: Perm[]; onDone: () => void }) {
  const [chosen, setChosen] = useState<string[]>(['leads.view']);
  const [busy, setBusy] = useState(false);

  async function approve() {
    setBusy(true);
    await api(`/admin/users/${user.id}/approve`, { method: 'POST', body: { permissions: chosen } });
    onDone();
  }

  return (
    <div className="card space-y-3 p-4">
      <div>
        <p className="font-semibold">{user.name}</p>
        <p className="text-sm text-slate-500">{user.email}{user.phone ? ` · ${user.phone}` : ''} · signed up {new Date(user.created_at).toLocaleDateString('en-IN')}</p>
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
      <button disabled={busy} onClick={approve} className="btn-dark">Approve</button>
    </div>
  );
}
