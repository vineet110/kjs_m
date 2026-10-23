'use client';
// Shared frame for /employee and /admin pages: loads "who am I", shows a sidebar
// filtered by permissions, and sends people to login when their session has ended.
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useEffect, useState } from 'react';
import { api, ApiFailure, type Me } from '@/lib/api';

const MeContext = createContext<Me | null>(null);
export const useMe = () => useContext(MeContext)!;

// One sidebar config for everyone; each link names the permission it needs (null = everyone).
const NAV: { href: string; label: string; perm: string | null; phase?: string }[] = [
  { href: '/employee/dashboard', label: 'My day', perm: null },
  { href: '/admin/dashboard', label: 'Admin overview', perm: 'staff.approve' },
  { href: '/admin/products', label: 'Products', perm: 'catalog.edit' },
  { href: '/admin/audit', label: 'Audit log', perm: 'audit.view' },
  { href: '/employee/attendance', label: 'Attendance', perm: null, phase: 'Phase 3' },
  { href: '/employee/tasks', label: 'Tasks', perm: null, phase: 'Phase 3' },
  { href: '/admin/auto-assign', label: 'Auto-assign', perm: 'staff.approve', phase: 'Phase 4' },
  { href: '/admin/order-boards', label: 'Order boards', perm: 'staff.approve', phase: 'Phase 5' },
  { href: '/admin/team-attendance', label: 'Team attendance', perm: 'staff.approve', phase: 'Phase 3' },
  { href: '/admin/approvals', label: 'Approvals', perm: 'staff.approve', phase: 'Phase 6' },
  { href: '/admin/analytics', label: 'Insights', perm: 'staff.approve', phase: 'Phase 6' },
];

export default function PortalShell({ children, requirePerm }: { children: React.ReactNode; requirePerm?: string }) {
  const [me, setMe] = useState<Me | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    api<Me>('/auth/me')
      .then((m) => {
        if (requirePerm && !m.permissions.includes(requirePerm)) router.replace('/employee/dashboard');
        else setMe(m);
      })
      .catch((e) => {
        if (e instanceof ApiFailure && e.status === 401) router.replace(`/employee/login?next=${encodeURIComponent(pathname)}`);
      });
  }, [requirePerm, router, pathname]);

  async function logout() {
    await api('/auth/logout', { method: 'POST' }).catch(() => undefined);
    router.replace('/employee/login');
  }

  if (!me) return <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">Loading…</div>;

  const links = NAV.filter((n) => n.perm === null || me.permissions.includes(n.perm));
  return (
    <MeContext.Provider value={me}>
      <div className="flex min-h-screen bg-slate-50">
        <aside className="hidden w-60 shrink-0 flex-col bg-forest text-emerald-50 md:flex">
          <div className="p-4">
            <Image src="/images/kjs/logo/Kjs.png" alt="KJS India" width={120} height={28} className="h-7 w-auto" />
            <p className="mt-1 text-[11px] uppercase tracking-widest text-emerald-300">{me.role === 'admin' ? 'Admin console' : 'Employee portal'}</p>
          </div>
          <nav className="flex-1 space-y-0.5 px-2">
            {links.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={`flex items-center justify-between rounded-md px-3 py-2 text-sm ${pathname.startsWith(n.href) ? 'bg-white/15 font-semibold text-white' : 'text-emerald-100 hover:bg-white/10'}`}
              >
                {n.label}
                {n.phase && <span className="text-[10px] text-emerald-300/70">{n.phase}</span>}
              </Link>
            ))}
          </nav>
          <div className="border-t border-white/10 p-4 text-xs">
            <p className="font-semibold text-white">{me.name}</p>
            <p className="truncate text-emerald-200">{me.email}</p>
            <button onClick={logout} className="mt-2 text-emerald-200 underline hover:text-white">Log out</button>
          </div>
        </aside>
        <div className="flex-1">
          <header className="flex items-center justify-between border-b bg-white px-4 py-3 md:hidden">
            <span className="font-semibold">KJS {me.role === 'admin' ? 'Admin' : 'Portal'}</span>
            <button onClick={logout} className="text-sm underline">Log out</button>
          </header>
          <div className="mx-auto max-w-6xl p-4 md:p-8">{children}</div>
        </div>
      </div>
    </MeContext.Provider>
  );
}

export function ComingSoon({ title, phase, what }: { title: string; phase: string; what: string }) {
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold">{title}</h1>
      <div className="card p-6 text-sm text-slate-600">
        <p className="font-semibold text-slate-900">Coming in {phase}</p>
        <p className="mt-1">{what}</p>
      </div>
    </div>
  );
}
