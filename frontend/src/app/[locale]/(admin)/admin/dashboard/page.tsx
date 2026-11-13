'use client';
// Screen 09 (first slice): real numbers + approve new staff with per-person permissions (D5).
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import ApproveCard, { type Perm, type StaffUser as User } from '@/components/portal/ApproveCard';
import { useMe } from '@/components/portal/PortalShell';
import StatTile from '@/components/portal/StatTile';
import { EmptyState } from '@/components/portal/ui';
import { Icon, type IconName } from '@/components/portal/icons';
import { api } from '@/lib/api';
import { canSee } from '@/lib/modules';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

type Stats = {
  leads_total: number; leads_new: number; leads_this_week: number; leads_last_week: number;
  // null: All Products is switched off (config/modules.ini)
  staff_pending: number; staff_active: number; products: number | null; categories: number | null;
};

/** "Good morning" / "Good afternoon" / "Good evening" by the time in India (where the team works). */
function greeting() {
  const h = Number(new Date().toLocaleString('en-GB', { hour: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' }));
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

/** "Tuesday, 3 November" in India time. */
function todayLong() {
  return new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Asia/Kolkata' });
}

/** "3 people" / "1 person", "5 new leads" / "1 new lead". */
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export default function AdminDashboard() {
  const me = useMe();
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [perms, setPerms] = useState<Perm[]>([]);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, u, p] = await Promise.all([api<Stats>('/admin/stats'), api<User[]>('/admin/users'), api<Perm[]>('/admin/permissions')]);
      setStats(s);
      setUsers(u);
      setPerms(p);
    } catch (e) {
      setError(e);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (error) return <LoadError error={error} onRetry={load} />;
  if (!stats) return <Loading />;

  const pending = users.filter((u) => u.status === 'pending');
  const others = users.filter((u) => u.status !== 'pending' && u.status !== 'rejected'); // rejected: in Approvals
  // Links only to pages this person can open (the sidebar hides the others too)
  const can = (p: string) => me.role === 'admin' || me.permissions.includes(p);
  const leadsHref = can('leads.view_all') ? '/admin/leads' : '/employee/dashboard';

  // One short line under the greeting: what needs attention, or "all caught up"
  const todo = [
    stats.staff_pending > 0 && `${plural(stats.staff_pending, 'person is', 'people are')} waiting for approval`,
    stats.leads_new > 0 && `${plural(stats.leads_new, 'new lead', 'new leads')} to look at`,
  ].filter(Boolean);
  const summary = todo.length ? `${todo.join(' and ')}.` : 'All caught up. Nothing needs you right now ✨';

  const actions: { label: string; href: string; icon: IconName; show: boolean }[] = [
    { label: 'Approve staff', href: '#approvals', icon: 'check', show: stats.staff_pending > 0 },
    { label: 'View new leads', href: leadsHref, icon: 'inbox', show: true },
    { label: 'Add product', href: '/admin/products', icon: 'plus', show: can('catalog.edit') && canSee(me, 'website_admin') },
  ];

  return (
    <div className="space-y-8">
      {/* Greeting: name, date, and what needs attention today */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{todayLong()}</p>
          <h1 className="mt-1 text-2xl font-bold md:text-3xl">
            {greeting()}, {me.name.split(' ')[0]} <span aria-hidden>👋</span>
          </h1>
          <p className="mt-1 text-sm text-slate-600">{summary}</p>
        </div>
        <p className="flex items-center gap-2 text-xs text-slate-500">
          <span aria-hidden className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75 motion-reduce:animate-none" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
          </span>
          Live numbers
        </p>
      </div>

      {/* Quick actions: the things an admin does most, one click away */}
      <div className="flex flex-wrap gap-2">
        {actions.filter((a) => a.show).map((a, i) => (
          <Link key={a.label} href={a.href} className={i === 0 ? 'btn-gold' : 'btn-ghost'}>
            <Icon name={a.icon} className="h-4 w-4" />
            {a.label}
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <StatTile label="New leads" value={stats.leads_new} icon="inbox" tone="blue" href={leadsHref} alert={stats.leads_new > 0} hint="Not contacted yet" />
        <StatTile label="Leads this week" value={stats.leads_this_week} icon="chart" tone="violet" href={leadsHref}
          trend={{ now: stats.leads_this_week, before: stats.leads_last_week }} />
        <StatTile label="All leads" value={stats.leads_total} icon="list" tone="slate" href={leadsHref} hint="Since the start" />
        <StatTile label="Waiting for approval" value={stats.staff_pending} icon="clock" tone="gold" href="#approvals"
          alert={stats.staff_pending > 0} hint={stats.staff_pending ? 'New staff sign-ups' : 'No one waiting'} />
        <StatTile label="Active staff" value={stats.staff_active} icon="users" tone="green" href="#staff" hint="Approved accounts" />
        {stats.products !== null && (
          <StatTile label="Products" value={stats.products} icon="box" tone="gold" href="/admin/products"
            hint={plural(stats.categories ?? 0, 'category', 'categories')} />
        )}
      </div>

      <section id="approvals" className="scroll-mt-6 space-y-3">
        <h2 className="text-lg font-bold">Waiting for approval ({pending.length})</h2>
        {pending.length === 0 && <EmptyState tone="done" title="All caught up!" text="No one is waiting for approval. New sign-ups will show here." />}
        {pending.map((u) => <ApproveCard key={u.id} user={u} perms={perms} onDone={load} />)}
      </section>

      <section id="staff" className="scroll-mt-6 space-y-3">
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
                    {/* Staff are managed in one place: Manage employees (edit, permissions, disable / enable) */}
                    {me.role === 'admin' && u.id !== me.id && (
                      <Link href={`/admin/users/${u.id}`} className="text-xs font-semibold underline">Edit</Link>
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
