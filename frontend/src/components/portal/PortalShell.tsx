'use client';
// Shared frame for /employee and /admin pages: loads "who am I", shows a sidebar
// filtered by permissions, and sends people to login when their session has ended.
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useEffect, useState } from 'react';
import { api, ApiFailure, type Me } from '@/lib/api';
import Bell from './Bell';

const MeContext = createContext<Me | null>(null);
export const useMe = () => useContext(MeContext)!;

// One sidebar config for everyone; each link names the permission it needs (null = every staff
// member, a list = any one of them). `soon` = page not built yet (see docs/checklist.md).
type NavItem = { href: string; label: string; perm: string | string[] | null; soon?: boolean };
const allowed = (perm: NavItem['perm'], mine: string[]) =>
  perm === null || (Array.isArray(perm) ? perm.some((p) => mine.includes(p)) : mine.includes(perm));
const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: 'My work',
    items: [
      { href: '/employee/dashboard', label: 'My day', perm: null },
      { href: '/employee/attendance', label: 'Attendance', perm: null },
      { href: '/employee/tasks', label: 'My tasks', perm: null },
      { href: '/employee/batches', label: 'My batches', perm: null },
      { href: '/employee/order-boards', label: 'Order boards', perm: null },
      { href: '/employee/me', label: 'Profile', perm: null },
    ],
  },
  {
    group: 'Admin',
    items: [
      { href: '/admin/dashboard', label: 'Overview', perm: 'staff.approve' },
      { href: '/admin/leads', label: 'All leads', perm: 'leads.view_all' },
      { href: '/admin/approvals', label: 'Approvals', perm: ['staff.approve', 'attendance.manage', 'files.approve'] },
      { href: '/admin/team-attendance', label: 'Team attendance', perm: 'attendance.manage' },
      { href: '/admin/order-boards', label: 'Order boards', perm: 'boards.manage' },
      { href: '/admin/auto-assign', label: 'Auto-assign', perm: 'assign.manage' },
      { href: '/admin/products', label: 'Products', perm: 'catalog.edit' },
      { href: '/admin/website', label: 'Website & partners', perm: ['content.edit', 'leads.view_all'] },
      { href: '/admin/koko', label: 'Koko', perm: 'content.edit' },
      { href: '/admin/holidays', label: 'Holidays', perm: 'calendar.edit' },
      { href: '/admin/analytics', label: 'Analytics', perm: 'staff.approve' },
      { href: '/admin/alerts', label: 'Alerts', perm: 'staff.approve' },
      { href: '/admin/audit', label: 'Audit log', perm: 'audit.view' },
      { href: '/admin/settings', label: 'Settings', perm: 'staff.approve' },
    ],
  },
];

export default function PortalShell({ children, requirePerm }: { children: React.ReactNode; requirePerm?: string }) {
  const [me, setMe] = useState<Me | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
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

  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((n) => allowed(n.perm, me.permissions)) }))
    .filter((g) => g.items.length > 0);
  return (
    <MeContext.Provider value={me}>
      <div className="flex min-h-screen bg-slate-50">
        <aside className={`${menuOpen ? 'fixed inset-y-0 left-0 z-40 flex' : 'hidden'} w-64 shrink-0 flex-col bg-forest text-emerald-50 md:static md:flex md:w-60`}>
          <div className="p-4">
            <Image src="/images/kjs/logo/Kjs.png" alt="KJS India" width={120} height={28} className="h-7 w-auto" />
            <p className="mt-1 text-[11px] uppercase tracking-widest text-emerald-300">{me.role === 'admin' ? 'Admin console' : 'Employee portal'}</p>
          </div>
          <nav className="flex-1 space-y-4 overflow-y-auto px-2">
            {groups.map((g) => (
              <div key={g.group} className="space-y-0.5">
                {groups.length > 1 && <p className="px-3 pb-1 text-[10px] font-bold uppercase tracking-widest text-emerald-300/80">{g.group}</p>}
                {g.items.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    onClick={() => setMenuOpen(false)}
                    className={`flex items-center justify-between rounded-md px-3 py-2 text-sm ${pathname.startsWith(n.href) ? 'bg-white/15 font-semibold text-white' : 'text-emerald-100 hover:bg-white/10'}`}
                  >
                    {n.label}
                    {n.soon && <span className="text-[10px] text-emerald-300/70">soon</span>}
                  </Link>
                ))}
              </div>
            ))}
          </nav>
          <div className="border-t border-white/10 p-4 text-xs">
            <p className="font-semibold text-white">{me.name}</p>
            <p className="truncate text-emerald-200">{me.email}</p>
            <button onClick={logout} className="mt-2 text-emerald-200 underline hover:text-white">Log out</button>
          </div>
        </aside>
        {menuOpen && <div className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={() => setMenuOpen(false)} />}
        <div className="min-w-0 flex-1">
          <header className="flex items-center justify-between gap-2 border-b bg-white px-4 py-2">
            <button onClick={() => setMenuOpen(true)} className="rounded p-2 hover:bg-slate-100 md:hidden" aria-label="Open menu">☰</button>
            <span className="font-semibold md:hidden">KJS {me.role === 'admin' ? 'Admin' : 'Portal'}</span>
            <div className="ml-auto flex items-center gap-2">
              <Bell />
              <button onClick={logout} className="text-sm underline md:hidden">Log out</button>
            </div>
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
