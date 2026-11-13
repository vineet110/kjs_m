'use client';
// Manage employees: every staff account, the one place to manage staff. Tabs by status (Accepted, Rejected,
// Pending, Disabled, All) with counts. Row actions: Edit (the User form), Permissions (the same page, at its
// Permissions box), Disable / Enable. "+ Create user" opens the User Creation Form.
// Who may do what (the server checks it too): editing and permissions are an admin's; anyone who manages
// staff may disable, only an admin turns an account back on. Nobody acts on their own account here.
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import DataTable, { type RowAction } from '@/components/portal/DataTable';
import { useMe } from '@/components/portal/PortalShell';
import { useToast } from '@/components/portal/Toast';
import { PageTitle, Pill } from '@/components/portal/ui';
import { api, ApiFailure, type StaffUser } from '@/lib/api';
import LoadError from '@/components/ui/LoadError';

type Tab = 'active' | 'rejected' | 'pending' | 'disabled' | 'all';
const TABS: [Tab, string][] = [['active', 'Accepted'], ['rejected', 'Rejected'], ['pending', 'Pending'], ['disabled', 'Disabled'], ['all', 'All']];

export default function UsersPage() {
  const me = useMe();
  const toast = useToast();
  const [rows, setRows] = useState<StaffUser[] | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const [tab, setTab] = useState<Tab>('active');
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
  const count = (t: Tab) => (rows ?? []).filter((u) => t === 'all' || u.status === t).length;
  const shown = rows === null ? null : rows.filter((u) => tab === 'all' || u.status === tab);
  const admin = me.role === 'admin';

  async function setStatus(u: StaffUser, status: 'active' | 'disabled') {
    const verb = status === 'disabled' ? 'Disable' : 'Enable';
    if (!confirm(`${verb} ${u.name}?${status === 'disabled' ? ' They are logged out at once and can no longer log in.' : ''}`)) return;
    try {
      await api(`/admin/users/${u.id}/status`, { method: 'POST', body: { status } });
      toast(`${u.name} is ${status === 'disabled' ? 'disabled' : 'enabled again'}`);
      load();
    } catch (e) {
      toast(e instanceof ApiFailure ? e.message : 'Could not change it. Please try again.', 'error');
    }
  }

  function actions(u: StaffUser): RowAction[] {
    if (u.id === me.id) return [];
    if (u.status === 'pending' || u.status === 'rejected') {
      // A sign-up is decided in Approvals (approve sets the permissions, reject needs a reason)
      return [{ label: u.status === 'pending' ? 'Approve or reject' : 'See in Approvals', href: '/admin/approvals' }];
    }
    const out: RowAction[] = [];
    if (admin) out.push({ label: 'Edit', href: `/admin/users/${u.id}` });
    if (admin && u.role !== 'admin') out.push({ label: 'Permissions', href: `/admin/users/${u.id}#permissions` });
    if (u.status === 'active' && (admin || u.role !== 'admin')) out.push({ label: 'Disable', onClick: () => setStatus(u, 'disabled') });
    if (u.status === 'disabled' && admin) out.push({ label: 'Enable', onClick: () => setStatus(u, 'active') });
    return out;
  }

  return (
    <div className="space-y-5">
      <PageTitle title="Manage employees" sub="Staff accounts. New sign-ups are approved or rejected in All approvals.">
        {admin && <Link href="/admin/users/new" className="btn-dark">+ Create user</Link>}
      </PageTitle>
      <div className="flex flex-wrap gap-2 text-sm" role="group" aria-label="Show">
        {TABS.map(([t, label]) => (
          <button key={t} type="button" onClick={() => setTab(t)} aria-pressed={tab === t}
            className={`rounded-full px-3 py-1 ${tab === t ? 'bg-ink text-white' : 'bg-white ring-1 ring-slate-200'}`}>
            {label} ({count(t)})
          </button>
        ))}
      </div>
      {loadErr != null && <LoadError error={loadErr} onRetry={load} />}
      <DataTable
        rows={shown}
        rowKey={(u) => u.id}
        noun="Users"
        search={(u) => `${u.name} ${u.email} ${u.phone ?? ''} ${u.employee_code} ${u.branch} ${u.job_title ?? ''}`}
        empty={{ title: tab === 'all' ? 'No users yet' : `No ${TABS.find(([t]) => t === tab)![1].toLowerCase()} employees` }}
        columns={[
          { label: 'Name', cell: (u) => admin && u.id !== me.id
            ? <Link href={`/admin/users/${u.id}`} className="font-medium text-sky-700 hover:underline">{u.name}</Link>
            : <span className="font-medium">{u.name}</span> },
          { label: 'Email', className: 'max-w-[14rem] truncate', cell: (u) => u.email },
          { label: 'Employee Code', cell: (u) => u.employee_code || '—' },
          { label: 'Department', cell: (u) => u.branch || '—' },
          { label: 'Job title', cell: (u) => u.job_title || '—' },
          { label: 'Access', cell: (u) => (u.role === 'admin' ? 'Admin' : 'Employee') },
          { label: 'Reporting To', cell: (u) => (u.reporting_to ? names.get(u.reporting_to) ?? '—' : '—') },
          { label: 'Status', cell: (u) => (
            <span title={u.status === 'rejected' && u.rejection_reason ? `Reason: ${u.rejection_reason}` : undefined}>
              <Pill value={u.status === 'disabled' ? 'rejected' : u.status === 'rejected' ? 'off' : u.status} label={u.status === 'active' ? 'accepted' : u.status} />
            </span>
          ) },
        ]}
        actions={actions}
      />
    </div>
  );
}
