'use client';
// Shared frame for /employee and /admin pages: loads "who am I", shows a sidebar
// filtered by permissions (hidden until the ☰ button slides it in), and sends people to login when
// their session has ended.
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api, ApiFailure, type Me } from '@/lib/api';
import { accountEpoch, forgetAccount, rememberAccount, rememberedAccount } from '@/lib/portal-session';
import AccountMenu, { Avatar, LogoutDialog, LogoutIcon, RoleBadge } from './AccountMenu';
import Bell from './Bell';
import SidebarNav from './SidebarNav';
import { ToastProvider } from './Toast';
import Loading from '@/components/ui/Loading';
import { asset } from '@/lib/assets';

const MeContext = createContext<Me | null>(null);
export const useMe = () => useContext(MeContext)!;

// "Who am I", asked on every page: loading, ready (the account), or error (server down, unreachable, or no
// answer within ME_TIMEOUT_MS: never a wait with no end). "Logged out" goes to the login page instead.
type Status = { state: 'loading' } | { state: 'ready'; me: Me } | { state: 'error'; requestId: string | null };
const ME_TIMEOUT_MS = 15_000;

// The account is remembered for the tab (lib/portal-session.ts): moving between admin and employee pages
// then shows the page at once.

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
  const [status, setStatus] = useState<Status>(() => {
    const known = rememberedAccount();
    return known && (!requirePerm || known.permissions.includes(requirePerm)) ? { state: 'ready', me: known } : { state: 'loading' };
  });
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
  const [confirmLogout, setConfirmLogout] = useState(false); // the "See you soon" popup
  const [loggingOut, setLoggingOut] = useState(false);
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
    const askedAt = accountEpoch();
    api<Me>('/auth/me', { timeoutMs: ME_TIMEOUT_MS })
      .then((m) => {
        if (n !== latest.current) return; // an older question, or this frame is gone / logging out
        rememberAccount(m, askedAt);
        if (requirePerm && !m.permissions.includes(requirePerm)) router.replace('/employee/dashboard');
        else setStatus({ state: 'ready', me: m });
      })
      .catch((e) => {
        if (n !== latest.current) return;
        if (e instanceof ApiFailure && e.status === 401) {
          forgetAccount();
          router.replace(`/employee/login?next=${encodeURIComponent(pathname)}`);
        }
        // A page already showing keeps showing (one failed re-check); else say so, with the error code
        else setStatus((s) => (s.state === 'ready' ? s : { state: 'error', requestId: e instanceof ApiFailure ? e.body.request_id : null }));
      });
  }, [requirePerm, router, pathname]);

  useEffect(() => {
    loadMe();
  }, [loadMe]);
  // Frame gone (left the portal): answers still on their way are ignored
  useEffect(() => () => void latest.current++, []);

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
      // Not while the logout popup is up: its Escape only closes the popup
      if (e.key !== 'Escape' || e.defaultPrevented || confirmLogout) return;
      const at = document.activeElement;
      if (overlay || sidebar.current?.contains(at) || at === menuButton.current) setMenu(false, { focusButton: true });
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [menuOpen, overlay, confirmLogout]);

  // Phone, menu open: the page behind it can't be scrolled (it is also `inert`, see the render)
  useEffect(() => {
    if (!overlay) return;
    const before = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = before;
    };
  }, [overlay]);

  // Goes to the login page even if the server is silent or fails (the error screen offers this exactly then).
  // `?bye=1` makes the login page say "You've logged out safely".
  async function logout() {
    setLoggingOut(true);
    latest.current++; // a "who am I" still on its way is ignored (no page update, nothing remembered)
    forgetAccount();
    await api('/auth/logout', { method: 'POST', timeoutMs: 5_000 }).catch(() => undefined);
    router.replace('/employee/login?bye=1');
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
  const isAttendance = pathname.includes('/employee/attendance');

  // Sidebar: always on the page, slid out of view when closed (a smooth slide both ways; none for "reduce
  // motion"). Closed, it is `inert`: its links can't be reached with Tab or a screen reader. On a computer the
  // page moves aside at once to make room (only the sidebar is animated: animating the page's width would make
  // big tables stutter); on a phone it slides OVER the page, with a backdrop and its own ✕, and the page
  // behind it is `inert` until it closes.
  return (
    <MeContext.Provider value={me}>
      <ToastProvider>
      <div className={isAttendance ? "h-screen w-screen overflow-hidden flex flex-col bg-white select-none" : "min-h-screen bg-paper"}>
        <aside
          ref={sidebar}
          id="portal-sidebar"
          inert={!menuOpen}
          className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-white/5 bg-gradient-to-b from-ink to-ink-soft text-stone-200 transition-transform duration-300 ease-out motion-reduce:transition-none md:w-60 ${menuOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full'}`}
        >
          <div className="relative p-4">
            {/* Phone: the open sidebar covers the ☰/✕ button in the top bar, so it has its own */}
            <button
              onClick={() => setMenu(false, { focusButton: true })}
              aria-label="Close menu"
              className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded text-lg text-stone-300 hover:bg-white/10 md:hidden"
            >
              <span aria-hidden>✕</span>
            </button>
            <Image src={asset('/images/kjs/logo/Kjs.png')} alt="KJS India" width={120} height={28} className="h-7 w-auto" />
            <p className="mt-1 text-[11px] uppercase tracking-widest text-gold">{me.role === 'admin' ? 'Admin console' : 'Employee portal'}</p>
          </div>
          {/* The links: groups open and close, and can be dragged into any order (SidebarNav) */}
          <SidebarNav me={me} pathname={pathname} onNavigate={() => isPhone && setMenu(false, { focusButton: true })} />
          {/* Profile card: who is logged in, and Log out (asks first, like the top-right menu) */}
          <div className="border-t border-white/10 p-3">
            <div className="flex items-center gap-3 rounded-lg bg-white/5 p-2">
              <Avatar name={me.name} className="h-9 w-9 text-sm ring-offset-ink" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-white">{me.name}</p>
                <RoleBadge role={me.role} dark />
              </div>
            </div>
            <button
              onClick={() => setConfirmLogout(true)}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-white/15 px-3 py-2 text-sm font-semibold text-stone-300 transition-colors hover:border-red-400/60 hover:bg-red-500/15 hover:text-white"
            >
              <LogoutIcon />
              Log out
            </button>
          </div>
        </aside>
        {menuOpen && <div aria-hidden className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={() => setMenu(false, { focusButton: true })} />}
        <div inert={overlay} className={`min-w-0 ${isAttendance ? 'flex-1 flex flex-col overflow-hidden' : ''} ${menuOpen ? 'md:pl-60' : ''}`}>
          <header className={`sticky top-0 z-20 flex h-11 items-center justify-between gap-2 border-b border-stone-200 bg-white px-4 shrink-0 ${isAttendance ? 'shadow-none' : 'backdrop-blur'}`}>
            <div className="flex items-center gap-3">
              <button
                ref={menuButton}
                onClick={() => setMenu(!menuOpen)}
                aria-expanded={menuOpen}
                aria-controls="portal-sidebar"
                aria-label={menuOpen ? 'Close menu' : 'Open menu'}
                className="flex h-8 w-8 items-center justify-center rounded text-base hover:bg-stone-100"
              >
                <span aria-hidden>{menuOpen ? '✕' : '☰'}</span>
              </button>
              <span className="font-semibold text-sm text-slate-800">KJS {me.role === 'admin' ? 'Admin' : 'Portal'}</span>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Bell />
              {/* Avatar menu with Log out, on every screen: the sidebar (with its own Log out) starts hidden */}
              <AccountMenu me={me} onLogout={() => setConfirmLogout(true)} />
            </div>
          </header>
          {/* Full-bleed for full-screen attendance workspace, padded container for standard pages */}
          {isAttendance ? (
            <div key={pathname} className="flex-1 w-full overflow-hidden flex flex-col">
              {children}
            </div>
          ) : (
            <div key={pathname} className="mx-auto max-w-6xl p-4 animate-in fade-in slide-in-from-bottom-1 duration-300 motion-reduce:animate-none md:p-8">
              {children}
            </div>
          )}
        </div>
        {/* Outside the `inert` page and sidebar, so it works whichever one opened it */}
        <LogoutDialog open={confirmLogout} name={me.name} busy={loggingOut} onConfirm={logout} onClose={() => setConfirmLogout(false)} />
      </div>
      </ToastProvider>
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
