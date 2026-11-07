'use client';
// Users > edit one person (same form as creating; the email can't change)
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import UserForm from '@/components/portal/UserForm';
import { EmptyState } from '@/components/portal/ui';
import Loading from '@/components/ui/Loading';
import { api, type StaffUser } from '@/lib/api';

export default function EditUserPage() {
  const { id } = useParams<{ id: string }>();
  const [user, setUser] = useState<StaffUser | null | undefined>(undefined);
  useEffect(() => {
    // No single-user route: the list is small, so pick the person from it
    api<StaffUser[]>('/admin/users').then((all) => setUser(all.find((u) => String(u.id) === id) ?? null)).catch(() => setUser(null));
  }, [id]);
  return (
    <div className="space-y-5">
      <nav aria-label="Breadcrumb" className="text-lg font-semibold">
        <Link href="/admin/users" className="hover:underline">Users</Link> <span className="text-slate-400">›</span> {user?.name ?? 'Edit user'}
      </nav>
      {user === undefined ? <Loading /> : user === null ? <EmptyState title="User not found" /> : <UserForm user={user} />}
    </div>
  );
}
