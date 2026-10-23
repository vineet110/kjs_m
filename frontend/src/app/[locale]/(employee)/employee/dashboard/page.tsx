'use client';
// E1 "My day" (first slice): greeting + leads to work on. Attendance, tasks and SLA timers come in Phase 3.
import LeadsTable from '@/components/portal/LeadsTable';
import { useMe } from '@/components/portal/PortalShell';

export default function EmployeeDashboard() {
  const me = useMe();
  const hour = Number(new Date().toLocaleString('en-IN', { hour: 'numeric', hour12: false, timeZone: 'Asia/Kolkata' }));
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{greet}, {me.name.split(' ')[0]}</h1>
        <p className="text-sm text-slate-500">Leads from the website and Koko. Mark them as you work on them.</p>
      </div>
      <LeadsTable />
    </div>
  );
}
