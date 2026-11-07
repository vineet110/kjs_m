'use client';
// Users > User Creation Form
import Link from 'next/link';
import UserForm from '@/components/portal/UserForm';

export default function NewUserPage() {
  return (
    <div className="space-y-5">
      <nav aria-label="Breadcrumb" className="text-lg font-semibold">
        <Link href="/admin/users" className="hover:underline">Users</Link> <span className="text-slate-400">›</span> User Creation Form
      </nav>
      <UserForm />
    </div>
  );
}
