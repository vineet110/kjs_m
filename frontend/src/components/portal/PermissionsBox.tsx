'use client';
// What an approved employee may do, changed after approval (Manage employees > edit). Admin only (the server
// checks it too). Saved with its own button; it applies on the person's next click, no log out needed.
// "See and work on leads" (leads.view) is always on. /admin/users/<id>#permissions opens the page at this box.
import { useEffect, useRef, useState } from 'react';
import { api, ApiFailure, type StaffUser } from '@/lib/api';
import type { Perm } from './ApproveCard';
import { useToast } from './Toast';

export default function PermissionsBox({ user, onSaved }: { user: StaffUser; onSaved: (u: StaffUser) => void }) {
  const [perms, setPerms] = useState<Perm[] | null>(null);
  const [chosen, setChosen] = useState<string[]>(user.permissions);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const box = useRef<HTMLElement>(null);
  const toast = useToast();

  useEffect(() => {
    api<Perm[]>('/admin/permissions').then(setPerms).catch(() => setErr('Could not load the permissions list.'));
  }, []);
  // Opened from "Permissions" in the list: bring the box into view once it is drawn
  useEffect(() => {
    if (perms && window.location.hash === '#permissions') box.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [perms]);

  const changed = [...chosen].sort().join() !== [...user.permissions].sort().join();

  async function save() {
    setBusy(true);
    setErr('');
    try {
      const u = await api<StaffUser>(`/admin/users/${user.id}/permissions`, { method: 'PUT', body: { permissions: chosen } });
      setChosen(u.permissions);
      onSaved(u);
      toast(`Saved. ${user.name.split(' ')[0]}'s new permissions apply on their next click`);
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section id="permissions" ref={box} className="card max-w-3xl scroll-mt-16 space-y-3 p-6">
      <div>
        <h2 className="text-xl font-semibold">Permissions</h2>
        <p className="text-sm text-slate-500">What {user.name.split(' ')[0]} may do in the portal. Changes apply on their next click.</p>
      </div>
      {perms === null && !err && <p className="text-sm text-slate-400">Loading…</p>}
      {perms && (
        <div className="grid gap-1 sm:grid-cols-2">
          {perms.map((p) => (
            <label key={p.key} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={chosen.includes(p.key)}
                disabled={p.key === 'leads.view' || busy}
                onChange={(e) => setChosen((c) => (e.target.checked ? [...c, p.key] : c.filter((k) => k !== p.key)))}
              />
              {p.label}
            </label>
          ))}
        </div>
      )}
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="flex gap-2">
        <button disabled={busy || !changed || !perms} onClick={save} className="btn-dark disabled:opacity-50">{busy ? 'Saving…' : 'Save permissions'}</button>
        {changed && <button disabled={busy} onClick={() => setChosen(user.permissions)} className="btn-ghost">Undo changes</button>}
      </div>
    </section>
  );
}
