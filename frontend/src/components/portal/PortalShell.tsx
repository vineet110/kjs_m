'use client';
// Shared frame for /employee and /admin pages: loads "who am I", shows a sidebar
// filtered by permissions (hidden until the ☰ button slides it in), and sends people to login when
// their session has ended.
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

// The sidebar. Phone = below Tailwind's `md` (768 px): there it slides OVER the page like a dialog; on a
// computer it moves the page aside. One constant for every check in code (the classes use `md:`).
const PHONE = '(max-width: 767px)';
const MENU_KEY = 'kjs_menu_open'; // this browser tab only: a new tab or a new visit starts hidden

/** Whether the screen is phone-sized, kept up to date when the window is resized. */
function useIsPhone() {
  const [phone, setPhone] = useState(false);
  useEffect(() => {
    const q = window.matchMedia(PHONE);
    setPhone(q.matches);
    const change = () => setPhone(q.matches);
    q.addEventListener('change', change);
    return () => q.removeEventListener('change', change);
  }, []);
  return phone;
}

export default function PortalShell({ children, requirePerm }: { children: React.ReactNode; requirePerm?: string }) {
  const [status, setStatus] = useState<Status>({ state: 'loading' });
  // The sidebar: hidden by default on every screen; the ☰ button slides it in and out (see the render below).
  // On a computer, an open sidebar stays open in this tab (also between admin and employee pages, which each
  // have their own frame, and after a reload); it is never reopened on a phone, where it would cover the page.
  // Read once when the frame starts, so a remembered sidebar is simply there (no slide on every page load).
  // The server has no window and gives false; the sidebar isn't drawn until the account has loaded anyway.
  const [menuOpen, setMenuOpen] = useState(() => {
    try {
      return typeof window !== 'undefined' && !window.matchMedia(PHONE).matches && sessionStorage.getItem(MENU_KEY) === '1';
    } catch {
      return false; // storage blocked (private mode): start hidden
    }
  });
  const isPhone = useIsPhone();
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const focusButtonAfterClose = useRef(false);
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

  // Opens or closes it, and remembers the choice for this tab (computer only; storage can be blocked in
  // private mode: then it just isn't remembered)
  function setMenu(open: boolean, { focusButton = false } = {}) {
    setMenuOpen(open);
    focusButtonAfterClose.current = !open && focusButton;
    try {
      if (!window.matchMedia(PHONE).matches) sessionStorage.setItem(MENU_KEY, open ? '1' : '0');
    } catch {}
  }
  // Closed from inside the sidebar (a link, the ✕, the backdrop, Escape): the keyboard focus would fall to the
  // top of the page as the sidebar becomes unreachable, so it goes to the ☰ button. After the close is drawn:
  // on a phone the button is unreachable (`inert`) while the menu is open.
  useEffect(() => {
    if (menuOpen || !focusButtonAfterClose.current) return;
    focusButtonAfterClose.current = false;
    menuButton.current?.focus();
  }, [menuOpen]);

  // Escape closes the sidebar, but only when it is "in use": the focus is in it or on its button, or it covers
  // the page (phone). Not for an Escape meant for something else (a form field, the Bell list).
  const overlay = menuOpen && isPhone;
  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return;
      const at = document.activeElement;
      if (overlay || sidebar.current?.contains(at) || at === menuButton.current) setMenu(false, { focusButton: true });
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [menuOpen, overlay]);

  // Phone, menu open: the page behind it can't be scrolled (it is also `inert`, see the render)
  useEffect(() => {
    if (!overlay) return;
    const before = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = before;
    };
  }, [overlay]);

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
  // Sidebar: always on the page, slid out of view when closed (a smooth slide both ways; none for "reduce
  // motion"). Closed, it is `inert`: its links can't be reached with Tab or a screen reader. On a computer the
  // page moves aside at once to make room (only the sidebar is animated: animating the page's width would make
  // big tables stutter); on a phone it slides OVER the page, with a backdrop and its own ✕, and the page
  // behind it is `inert` until it closes.
  return (
    <MeContext.Provider value={me}>
      <div className="min-h-screen bg-slate-50">
        <aside
          ref={sidebar}
          id="portal-sidebar"
          inert={!menuOpen}
          className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-forest text-emerald-50 transition-transform duration-300 ease-out motion-reduce:transition-none md:w-60 ${menuOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full'}`}
        >
          <div className="relative p-4">
            {/* Phone: the open sidebar covers the ☰/✕ button in the top bar, so it has its own */}
            <button
              onClick={() => setMenu(false, { focusButton: true })}
              aria-label="Close menu"
              className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded text-lg text-emerald-100 hover:bg-white/10 md:hidden"
            >
              <span aria-hidden>✕</span>
            </button>
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
                    // On a phone the open menu covers the page: close it. On a computer it stays open.
                    onClick={() => isPhone && setMenu(false, { focusButton: true })}
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
        {menuOpen && <div aria-hidden className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={() => setMenu(false, { focusButton: true })} />}
        <div inert={overlay} className={`min-w-0 ${menuOpen ? 'md:pl-60' : ''}`}>
          <header className="flex items-center justify-between gap-2 border-b bg-white px-4 py-2">
            <button
              ref={menuButton}
              onClick={() => setMenu(!menuOpen)}
              aria-expanded={menuOpen}
              aria-controls="portal-sidebar"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              className="flex h-9 w-9 items-center justify-center rounded text-lg hover:bg-slate-100"
            >
              <span aria-hidden>{menuOpen ? '✕' : '☰'}</span>
            </button>
            <span className="font-semibold">KJS {me.role === 'admin' ? 'Admin' : 'Portal'}</span>
            <div className="ml-auto flex items-center gap-2">
              <Bell />
              {/* Log out is here on every screen too: the sidebar (with its own Log out) starts hidden */}
              <button onClick={logout} className="text-sm underline">Log out</button>
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
