'use client';
// Users: every staff account, with the admin-set details (employee code, branch, role, reporting to).
// "+ Create user" opens the User Creation Form; a name opens the same form to edit that person.
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import DataTable from '@/components/portal/DataTable';
import { PageTitle, Pill } from '@/components/portal/ui';
import { api, type StaffUser } from '@/lib/api';
import LoadError from '@/components/ui/LoadError';

export default function UsersPage() {
  const [rows, setRows] = useState<StaffUser[] | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const load = useCallback(() => {
    setLoadErr(null);
    api<StaffUser[]>('/admin/users')
      .then(setRows)
      .catch((e) => { setRows([]); setLoadErr(e); });
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  const names = new Map((rows ?? []).map((u) => [u.id, u.name]));

  return (
    <div className="space-y-5">
      <PageTitle title="Manage employees" sub="Staff accounts. New sign-ups still wait in Approvals.">
        <Link href="/admin/users/new" className="btn-dark">+ Create user</Link>
      </PageTitle>
      {loadErr != null && <LoadError error={loadErr} onRetry={load} />}
      <DataTable
        rows={rows}
        rowKey={(u) => u.id}
        noun="Users"
        search={(u) => `${u.name} ${u.email} ${u.phone ?? ''} ${u.employee_code} ${u.branch}`}
        empty={{ title: 'No users yet' }}
        columns={[
          { label: 'Name', cell: (u) => <Link href={`/admin/users/${u.id}`} className="font-medium text-sky-700 hover:underline">{u.name}</Link> },
          { label: 'Email', className: 'max-w-[14rem] truncate', cell: (u) => u.email },
          { label: 'Employee Code', cell: (u) => u.employee_code || '—' },
          { label: 'Branch', cell: (u) => u.branch || '—' },
          { label: 'Role', className: 'capitalize', cell: (u) => u.role },
          { label: 'Reporting To', cell: (u) => (u.reporting_to ? names.get(u.reporting_to) ?? '—' : '—') },
          { label: 'Status', cell: (u) => <Pill value={u.status === 'disabled' ? 'rejected' : u.status} label={u.status} /> },
        ]}
        actions={(u) => [{ label: 'Edit', href: `/admin/users/${u.id}` }]}
      />
    </div>
  );
}
