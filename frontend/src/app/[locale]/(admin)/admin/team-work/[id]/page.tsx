'use client';
// One person's work (monitor.view). Opening it is written to the audit log (once per day per person).
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useState } from 'react';
import { PageTitle } from '@/components/portal/ui';
import WorkView from '@/components/portal/WorkView';
import type { WorkOverview } from '@/lib/api';

export default function PersonWork() {
  const { id } = useParams<{ id: string }>();
  const [who, setWho] = useState<WorkOverview | null>(null);
  const onPerson = useCallback((o: WorkOverview) => setWho(o), []);
  const t = who?.today;
  const status = t
    ? t.check_in ? `Checked in ${t.check_in}${t.check_out && !t.is_checked_in ? ` · out ${t.check_out}` : ''}` : 'Not checked in today'
    : '';

  return (
    <div className="space-y-6">
      <Link href="/admin/team-work" className="text-sm text-sky-700 hover:underline">← Team work</Link>
      <PageTitle title={who?.user.name ?? 'Employee'} sub={status} />
      <WorkView base={`/work/${Number(id)}`} onPerson={onPerson} />
      <p className="text-xs text-slate-500">Opening this page is recorded in the activity log.</p>
    </div>
  );
}
