'use client';
// Users > edit one person (same form as creating; the email can't change), and below it what they may do
// (Permissions: admin only, for an approved employee who isn't you).
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import PermissionsBox from '@/components/portal/PermissionsBox';
import { useMe } from '@/components/portal/PortalShell';
import UserForm from '@/components/portal/UserForm';
import { EmptyState } from '@/components/portal/ui';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';
import { api, type StaffUser } from '@/lib/api';

export default function EditUserPage() {
  const { id } = useParams<{ id: string }>();
  const [user, setUser] = useState<StaffUser | null | undefined>(undefined);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const me = useMe();
  const load = useCallback(() => {
    setLoadErr(null);
    // No single-user route: the list is small, so pick the person from it
    api<StaffUser[]>('/admin/users').then((all) => setUser(all.find((u) => String(u.id) === id) ?? null)).catch(setLoadErr);
  }, [id]);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <div className="space-y-5">
      <nav aria-label="Breadcrumb" className="text-lg font-semibold">
        <Link href="/admin/users" className="hover:underline">Users</Link> <span className="text-slate-400">›</span> {user?.name ?? 'Edit user'}
      </nav>
      {loadErr ? <LoadError error={loadErr} onRetry={load} /> : user === undefined ? <Loading /> : user === null ? <EmptyState title="User not found" /> : (
        <>
          <UserForm user={user} onSaved={setUser} />
          {me.role === 'admin' && user.id !== me.id && user.role !== 'admin' && (user.status === 'active' || user.status === 'disabled') && (
            <PermissionsBox user={user} onSaved={setUser} />
          )}
        </>
      )}
    </div>
  );
}
