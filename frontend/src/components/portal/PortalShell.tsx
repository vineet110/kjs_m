'use client';
// Shared frame for /employee and /admin pages: loads "who am I", shows a sidebar
// filtered by permissions, and sends people to login when their session has ended.
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api, ApiFailure, type Me } from '@/lib/api';
import Bell from './Bell';
import Loading from '@/components/ui/Loading';

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

// "Who am I", asked on every page: loading, ready (the account), or error (server down, unreachable, or no
// answer within ME_TIMEOUT_MS: never a wait with no end). "Logged out" goes to the login page instead.
type Status = { state: 'loading' } | { state: 'ready'; me: Me } | { state: 'error'; requestId: string | null };
const ME_TIMEOUT_MS = 15_000;

export default function PortalShell({ children, requirePerm }: { children: React.ReactNode; requirePerm?: string }) {
  const [status, setStatus] = useState<Status>({ state: 'loading' });
  const [menuOpen, setMenuOpen] = useState(false);
  const latest = useRef(0); // only the newest answer counts (an older, slower one is ignored)
  const router = useRouter();
  const pathname = usePathname();

  const loadMe = useCallback(() => {
    const n = ++latest.current;
    // After an error (a page change, Back, or "Try again"): the spinner while asking again. A page that is
    // already showing stays as it is while its account is re-checked.
    setStatus((s) => (s.state === 'error' ? { state: 'loading' } : s));
    api<Me>('/auth/me', { timeoutMs: ME_TIMEOUT_MS })
      .then((m) => {
        if (n !== latest.current) return;
        if (requirePerm && !m.permissions.includes(requirePerm)) router.replace('/employee/dashboard');
        else setStatus({ state: 'ready', me: m });
      })
      .catch((e) => {
        if (n !== latest.current) return;
        if (e instanceof ApiFailure && e.status === 401) router.replace(`/employee/login?next=${encodeURIComponent(pathname)}`);
        // A page already showing keeps showing (one failed re-check); else say so, with the error code
        else setStatus((s) => (s.state === 'ready' ? s : { state: 'error', requestId: e instanceof ApiFailure ? e.body.request_id : null }));
      });
  }, [requirePerm, router, pathname]);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  // Goes to the login page even if the server is silent or fails (the error screen offers this exactly then)
  async function logout() {
    await api('/auth/logout', { method: 'POST', timeoutMs: 5_000 }).catch(() => undefined);
    router.replace('/employee/login');
  }

  // While the account loads (also right after logging in: the login spinner carries on here). Each page
  // then shows its own Loading while its data comes.
  if (status.state === 'loading')
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loading />
      </div>
    );
  // Never a dead end: try again, or log out (the sidebar with Log out isn't shown without the account)
  if (status.state === 'error')
    return (
      <div role="alert" className="flex min-h-screen flex-col items-center justify-center gap-3 p-4 text-center text-sm text-slate-600">
        <p>Could not load your account. The server may be busy; please try again.</p>
        <div className="flex gap-2">
          <button onClick={loadMe} className="btn-dark">Try again</button>
          <button onClick={logout} className="btn-ghost">Log out</button>
        </div>
        {status.requestId && (
          <p className="text-xs text-slate-400">
            If this keeps happening, send this code to the admin: <span className="select-all font-mono">{status.requestId}</span>
          </p>
        )}
      </div>
    );
  const me = status.me;

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
