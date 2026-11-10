'use client';
// E1 "My day": attendance + availability, task numbers, then leads to work on (with SLA timers).
import Link from 'next/link';
import { useEffect, useState } from 'react';
import LeadsTable from '@/components/portal/LeadsTable';
import { useMe } from '@/components/portal/PortalShell';
import TodayCard from '@/components/portal/TodayCard';
import { api, type TaskStats } from '@/lib/api';
import { canSee } from '@/lib/modules';

export default function EmployeeDashboard() {
  const me = useMe();
  const [stats, setStats] = useState<TaskStats | null>(null);
  useEffect(() => {
    api<TaskStats>('/tasks/stats').then(setStats).catch(() => undefined);
  }, []);
  const hour = Number(new Date().toLocaleString('en-IN', { hour: 'numeric', hour12: false, timeZone: 'Asia/Kolkata' }));
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const tiles = stats ? [
    { label: 'Tasks', value: stats.total },
    { label: 'Done', value: stats.done },
    { label: 'Pending', value: stats.pending },
    { label: 'Overdue', value: stats.overdue, warn: stats.overdue > 0 },
  ] : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{greet}, {me.name.split(' ')[0]}</h1>
        <p className="text-sm text-slate-500">Your attendance, tasks and leads for today.</p>
      </div>
      {canSee(me, 'attendance') && <TodayCard />}
      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {tiles.map((t) => (
            <Link key={t.label} href="/employee/tasks" className="card p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">{t.label}</p>
              <p className={`mt-1 text-3xl font-bold ${t.warn ? 'text-red-700' : ''}`}>{t.value}</p>
            </Link>
          ))}
        </div>
      )}
      {me.permissions.includes('leads.view') && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold">My leads</h2>
          <LeadsTable />
        </section>
      )}
    </div>
  );
}
