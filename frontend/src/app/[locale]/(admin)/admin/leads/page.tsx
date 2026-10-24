'use client';
// All leads: owner, SLA status, reassign. SLA targets come from config/sla.ini.
import { useEffect, useState } from 'react';
import LeadsTable from '@/components/portal/LeadsTable';
import { PageTitle } from '@/components/portal/ui';
import { api } from '@/lib/api';

type Sla = { respond_minutes: number; resolve_minutes: number; escalate_after_minutes: number; work_hours: string };

export default function AdminLeads() {
  const [sla, setSla] = useState<Sla | null>(null);
  useEffect(() => {
    api<Sla>('/admin/sla').then(setSla);
  }, []);
  return (
    <div className="space-y-6">
      <PageTitle
        title="All leads"
        sub={sla ? `SLA: respond in ${sla.respond_minutes} min, close in ${sla.resolve_minutes} min (working hours ${sla.work_hours} IST). Admins are told ${sla.escalate_after_minutes} min after a miss.` : undefined}
      />
      <LeadsTable admin />
    </div>
  );
}
