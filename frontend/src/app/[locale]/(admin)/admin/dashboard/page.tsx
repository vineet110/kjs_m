'use client';
// Screen 09 (first slice): real numbers + approve new staff with per-person permissions (D5).
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import ApproveCard, { type Perm, type StaffUser as User } from '@/components/portal/ApproveCard';
import { api, ApiFailure } from '@/lib/api';

type Stats = { leads_total: number; leads_new: number; staff_pending: number; staff_active: number; products: number; categories: number };

export default function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [perms, setPerms] = useState<Perm[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [s, u, p] = await Promise.all([api<Stats>('/admin/stats'), api<User[]>('/admin/users'), api<Perm[]>('/admin/permissions')]);
      setStats(s);
      setUsers(u);
      setPerms(p);
    } catch (e) {
      setError(e instanceof ApiFailure ? e.message : 'Could not load.');
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (error) return <div className="card p-6 text-sm text-red-700">{error}</div>;
  if (!stats) return <p className="text-sm text-slate-500">Loading…</p>;

  const pending = users.filter((u) => u.status === 'pending');
  const others = users.filter((u) => u.status !== 'pending');
  const tiles = [
    { label: 'New leads', value: stats.leads_new, href: '/employee/dashboard' },
    { label: 'All leads', value: stats.leads_total, href: '/employee/dashboard' },
    { label: 'Waiting for approval', value: stats.staff_pending },
    { label: 'Active staff', value: stats.staff_active },
    { label: 'Products', value: stats.products, href: '/admin/products' },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Admin overview</h1>
        <p className="text-sm text-slate-500">Live numbers from the database.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {tiles.map((t) => {
          const body = (
            <div className="card p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">{t.label}</p>
              <p className={`mt-1 text-3xl font-bold ${t.label === 'Waiting for approval' && t.value ? 'text-gold-dark' : ''}`}>{t.value}</p>
            </div>
          );
          return t.href ? <Link key={t.label} href={t.href}>{body}</Link> : <div key={t.label}>{body}</div>;
        })}
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">Waiting for approval ({pending.length})</h2>
        {pending.length === 0 && <p className="card p-4 text-sm text-slate-500">No one is waiting.</p>}
        {pending.map((u) => <ApproveCard key={u.id} user={u} perms={perms} onDone={load} />)}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">Staff</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="p-3">Name</th><th className="p-3">Email</th><th className="p-3">Role</th><th className="p-3">Permissions</th><th className="p-3">Status</th><th className="p-3" /></tr>
            </thead>
            <tbody>
              {others.map((u) => (
                <tr key={u.id} className="border-t">
                  <td className="p-3 font-medium">{u.name}</td>
                  <td className="p-3">{u.email}</td>
                  <td className="p-3">{u.role}</td>
                  <td className="p-3 text-xs text-slate-500">{u.role === 'admin' ? 'all' : u.permissions.join(', ')}</td>
                  <td className="p-3">{u.status}</td>
                  <td className="p-3 text-right">
                    {u.role !== 'admin' && (
                      <button
                        className="text-xs underline"
                        onClick={async () => {
                          await api(`/admin/users/${u.id}/status`, { method: 'POST', body: { status: u.status === 'active' ? 'disabled' : 'active' } });
                          load();
                        }}
                      >
                        {u.status === 'active' ? 'Disable' : 'Enable'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
