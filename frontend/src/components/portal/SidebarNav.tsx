'use client';
// The sidebar's list of links. Groups (My work, Admin, People, …) open and close like a dropdown, and can be
// put in any order by dragging their grip (⋮⋮) or with the arrow keys on it. Both choices are remembered in
// this browser (localStorage: a per-person convenience, nothing on the server).
import Link from 'next/link';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { api, type Me } from '@/lib/api';
import { moveGroup, sortByOrder } from '@/lib/nav-order';
import { onApprovalsChanged } from '@/lib/portal-session';
import { Icon, type IconName } from './icons';

// One sidebar config for everyone; each link names the permission it needs (null = every staff
// member, a list = any one of them). `soon` = page not built yet (see docs/checklist.md).
// `badge` = the link shows a count of things waiting (see `useApprovalCount`).
type NavItem = { href: string; label: string; icon: IconName; perm: string | string[] | null; soon?: boolean; badge?: 'approvals' };
type NavGroup = { group: string; items: NavItem[] };
const allowed = (perm: NavItem['perm'], mine: string[]) =>
  perm === null || (Array.isArray(perm) ? perm.some((p) => mine.includes(p)) : mine.includes(perm));
const APPROVE_PERMS = ['staff.approve', 'attendance.manage', 'files.approve'];
const NAV: NavGroup[] = [
  {
    group: 'My work',
    items: [
      { href: '/employee/dashboard', label: 'My day', icon: 'sun', perm: null },
      { href: '/employee/attendance', label: 'Attendance', icon: 'clock', perm: null },
      { href: '/employee/batches', label: 'My batches', icon: 'layers', perm: null },
      { href: '/employee/order-boards', label: 'Order boards', icon: 'board', perm: null },
      { href: '/employee/me', label: 'Profile', icon: 'user', perm: null },
    ],
  },
  {
    // Same pages for admin and staff: leads.view_all sees everyone's leads, others their own + unassigned
    group: 'Lead Management',
    items: [
      { href: '/employee/contacts', label: 'Contacts', icon: 'contact', perm: 'leads.view' },
      { href: '/employee/tasks', label: 'Tasks', icon: 'tasks', perm: null },
      { href: '/employee/koko-leads', label: 'Koko Lead', icon: 'chat', perm: 'leads.view' },
      { href: '/employee/internal-leads', label: 'Internal lead', icon: 'userPlus', perm: 'leads.view' },
    ],
  },
  {
    group: 'Admin',
    items: [{ href: '/admin/dashboard', label: 'Overview', icon: 'home', perm: 'staff.approve' }],
  },
  {
    group: 'People',
    items: [
      { href: '/admin/approvals', label: 'Approvals', icon: 'check', perm: APPROVE_PERMS, badge: 'approvals' },
      { href: '/admin/users', label: 'Users', icon: 'users', perm: 'staff.approve' },
      { href: '/admin/team-attendance', label: 'Team attendance', icon: 'clock', perm: 'attendance.manage' },
    ],
  },
  {
    group: 'Sales',
    items: [
      { href: '/admin/leads', label: 'All leads', icon: 'inbox', perm: 'leads.view_all' },
      { href: '/admin/order-boards', label: 'Order boards', icon: 'board', perm: 'boards.manage' },
      { href: '/admin/auto-assign', label: 'Auto-assign', icon: 'shuffle', perm: 'assign.manage' },
      { href: '/admin/client-schedulers', label: 'Client Schedulers', icon: 'layers', perm: 'assign.manage' },
    ],
  },
  {
    group: 'Website',
    items: [
      { href: '/admin/products', label: 'Products', icon: 'box', perm: 'catalog.edit' },
      { href: '/admin/website', label: 'Website & partners', icon: 'globe', perm: ['content.edit', 'leads.view_all'] },
      { href: '/admin/koko', label: 'Koko', icon: 'chat', perm: 'content.edit' },
    ],
  },
  {
    group: 'System',
    items: [
      { href: '/admin/analytics', label: 'Analytics', icon: 'chart', perm: 'staff.approve' },
      { href: '/admin/alerts', label: 'Alerts', icon: 'bell', perm: 'staff.approve' },
      { href: '/admin/holidays', label: 'Holidays', icon: 'calendar', perm: 'calendar.edit' },
      { href: '/admin/audit', label: 'Audit log', icon: 'file', perm: 'audit.view' },
      { href: '/admin/settings', label: 'Settings', icon: 'settings', perm: 'staff.approve' },
    ],
  },
];
const DEFAULT_ORDER = NAV.map((g) => g.group);

type Inbox = { signups: unknown[] | null; regularizations: unknown[] | null; file_deletes: unknown[] | null };

/** How many things wait in the Approvals inbox (sign-ups + attendance fixes + file deletions you may
 * approve), for the sidebar badge. Asked in the background: it never holds up the page. Re-asked on each
 * page change, and right after an approve / reject on the page you are on (approvalsChanged()). 0 when you
 * can't approve. Only the newest answer counts, so a slow older one can't put an old number back. */
function useApprovalCount(enabled: boolean, pathname: string) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let latest = 0;
    const ask = () => {
      const mine = ++latest;
      api<Inbox>('/admin/approvals')
        .then((i) => mine === latest && setN((i.signups?.length ?? 0) + (i.regularizations?.length ?? 0) + (i.file_deletes?.length ?? 0)))
        .catch(() => undefined); // no badge is fine; the page itself shows any error
    };
    ask();
    const stop = onApprovalsChanged(ask);
    return () => {
      latest = -1; // ignore answers that come after this page / account
      stop();
    };
  }, [enabled, pathname]);
  return n;
}

// Remembered in this browser. Read/write can fail (private mode, blocked storage): then nothing is
// remembered and the defaults are used.
const ORDER_KEY = 'kjs_nav_order';
const OPEN_KEY = 'kjs_nav_open';
function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}
function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

const isActive = (pathname: string, href: string) => pathname.startsWith(href);

export default function SidebarNav({ me, pathname, onNavigate }: { me: Me; pathname: string; onNavigate: () => void }) {
  const approvals = useApprovalCount(allowed(APPROVE_PERMS, me.permissions), pathname);
  const visible = NAV.map((g) => ({ ...g, items: g.items.filter((n) => allowed(n.perm, me.permissions)) })).filter((g) => g.items.length > 0);
  const many = visible.length > 1; // one group (most staff): a plain list, no headers to open or drag

  const [order, setOrder] = useState<string[]>(() => {
    const saved = load<unknown>(ORDER_KEY, DEFAULT_ORDER);
    return Array.isArray(saved) ? saved.filter((x): x is string => typeof x === 'string') : DEFAULT_ORDER; // edited by hand: ignore
  });
  // Open or closed per group. Not chosen yet: only the group of the page you are on is open.
  const [open, setOpen] = useState<Record<string, boolean>>(() => {
    const saved = load<unknown>(OPEN_KEY, {});
    return saved && typeof saved === 'object' && !Array.isArray(saved) ? (saved as Record<string, boolean>) : {};
  });
  const groups = sortByOrder(visible.map((g) => g.group), order, DEFAULT_ORDER).map((n) => visible.find((g) => g.group === n)!);
  const activeGroup = visible.find((g) => g.items.some((n) => isActive(pathname, n.href)))?.group;
  const isOpen = (g: string) => !many || (open[g] ?? g === activeGroup);

  // Opening a page whose group is closed (a quick action, a link on a page): open that group, so the
  // current page is always visible in the sidebar
  useEffect(() => {
    if (activeGroup && open[activeGroup] === false) setOpen((o) => ({ ...o, [activeGroup]: true }));
  }, [activeGroup]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggle(g: string) {
    const next = { ...open, [g]: !isOpen(g) };
    setOpen(next);
    save(OPEN_KEY, next);
  }

  // ----- Reordering -----
  const [dragging, setDragging] = useState<string | null>(null);
  const [said, setSaid] = useState(''); // read out by screen readers after a move
  const orderNow = useRef(groups.map((g) => g.group));
  orderNow.current = groups.map((g) => g.group);

  /** Puts group `g` at place `to` among the groups you can see; the full order (incl. groups you can't
   * see) is kept, so another account in this browser doesn't lose its own places. */
  function moveTo(g: string, to: number) {
    const next = moveGroup(orderNow.current, order, DEFAULT_ORDER, g, to);
    setOrder(next);
    return next;
  }

  // Drag with the grip: pointer events work the same for mouse, touch and pen. While the pointer moves
  // over another group past its middle, the dragged group takes that group's place (the list changes
  // live, so you see where it will land). Saved when you let go.
  // The moves are followed on the whole window, not with pointer capture on the grip: when a group moves
  // down, React moves its block in the page, and a moved element loses its capture, so letting go was
  // never seen and the drag got stuck (PR #17 review).
  function onGripDown(e: React.PointerEvent<HTMLButtonElement>, g: string) {
    if (e.button !== 0) return;
    e.preventDefault();
    setDragging(g);
  }
  const dragRef = useRef<{ move: (e: PointerEvent) => void; up: () => void }>(null!);
  dragRef.current = { move: onDragMove, up: onDragUp }; // the newest versions (they read the current order)
  useEffect(() => {
    if (!dragging) return;
    const move = (e: PointerEvent) => dragRef.current.move(e);
    const up = () => dragRef.current.up();
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', up);
    };
  }, [dragging]);
  function onDragMove(e: PointerEvent) {
    if (!dragging) return;
    const over = document.elementFromPoint(e.clientX, e.clientY)?.closest<HTMLElement>('[data-nav-group]');
    const target = over?.dataset.navGroup;
    if (!over || !target || target === dragging) return;
    const from = orderNow.current.indexOf(dragging);
    const to = orderNow.current.indexOf(target);
    const r = over.getBoundingClientRect();
    const middle = r.top + r.height / 2;
    // Only past the middle of the other group, so two groups of different heights don't flip back and forth
    if ((to > from && e.clientY > middle) || (to < from && e.clientY < middle)) moveTo(dragging, to);
  }
  function onDragUp() {
    if (!dragging) return;
    save(ORDER_KEY, order);
    setSaid(`${dragging} moved to place ${orderNow.current.indexOf(dragging) + 1} of ${orderNow.current.length}.`);
    setDragging(null);
  }
  // Keyboard: arrow up / down on the grip moves the group one place. Moving its block in the page takes the
  // focus away, so the focus is put back on the same grip right after the move is drawn (PR #17 review).
  const grips = useRef<Record<string, HTMLButtonElement | null>>({});
  const refocus = useRef<string | null>(null);
  useLayoutEffect(() => {
    if (!refocus.current) return;
    grips.current[refocus.current]?.focus();
    refocus.current = null;
  }, [order]);
  function onGripKey(e: React.KeyboardEvent<HTMLButtonElement>, g: string) {
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
    e.preventDefault();
    const from = orderNow.current.indexOf(g);
    const to = e.key === 'ArrowUp' ? from - 1 : from + 1;
    if (to < 0 || to >= orderNow.current.length) return;
    refocus.current = g;
    save(ORDER_KEY, moveTo(g, to));
    setSaid(`${g} moved to place ${to + 1} of ${orderNow.current.length}.`);
  }
  function resetOrder() {
    setOrder(DEFAULT_ORDER);
    save(ORDER_KEY, DEFAULT_ORDER);
    setSaid('Groups are back in the first order.');
  }
  const custom = many && visible.some((g, i) => g.group !== groups[i].group); // `visible` is in the default order

  return (
    <nav aria-label="Portal" className={`flex-1 space-y-1 overflow-y-auto px-2 pb-2 ${dragging ? 'cursor-grabbing select-none' : ''}`}>
      {groups.map((g) => {
        const shown = isOpen(g.group);
        const listId = `nav-${g.group.replace(/\W+/g, '-').toLowerCase()}`;
        const waiting = g.items.some((n) => n.badge === 'approvals') ? approvals : 0;
        return (
          <div
            key={g.group}
            data-nav-group={g.group}
            className={`rounded-lg transition-colors ${dragging === g.group ? 'bg-white/10 ring-1 ring-gold/60' : ''}`}
          >
            {many && (
              <div className="group/head flex items-center">
                <button
                  type="button"
                  aria-label={`Move ${g.group}. Drag, or use the up and down arrow keys.`}
                  ref={(el) => {
                    grips.current[g.group] = el;
                  }}
                  onPointerDown={(e) => onGripDown(e, g.group)}
                  onKeyDown={(e) => onGripKey(e, g.group)}
                  // touch-none: on a phone, dragging the grip moves the group instead of scrolling the sidebar
                  className="flex h-8 w-6 shrink-0 cursor-grab touch-none items-center justify-center rounded text-stone-600 opacity-60 hover:text-stone-300 hover:opacity-100 focus-visible:opacity-100 group-hover/head:opacity-100"
                >
                  <Icon name="grip" className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => toggle(g.group)}
                  aria-expanded={shown}
                  aria-controls={listId}
                  className="flex flex-1 items-center gap-2 rounded-md py-2 pl-1 pr-2 text-left text-[11px] font-bold uppercase tracking-widest text-stone-400 hover:bg-white/5 hover:text-stone-200"
                >
                  <span className="flex-1">{g.group}</span>
                  {/* Closed: the count still shows on the group, so nothing waiting gets hidden */}
                  {!shown && waiting > 0 && (
                    <span className="min-w-[20px] rounded-full bg-gold px-1.5 text-center text-[11px] font-bold normal-case leading-5 tracking-normal text-ink">
                      {waiting > 99 ? '99+' : waiting}
                      <span className="sr-only"> waiting</span>
                    </span>
                  )}
                  <Icon name="chevron" className={`h-4 w-4 transition-transform duration-200 motion-reduce:transition-none ${shown ? 'rotate-180' : ''}`} />
                </button>
              </div>
            )}
            {shown && (
              <div id={listId} className={`space-y-0.5 pb-2 ${many ? 'animate-in fade-in slide-in-from-top-1 duration-150 motion-reduce:animate-none' : ''}`}>
                {g.items.map((n) => {
                  const active = isActive(pathname, n.href);
                  const count = n.badge === 'approvals' ? approvals : 0;
                  return (
                    <Link
                      key={n.href}
                      href={n.href}
                      aria-current={active ? 'page' : undefined}
                      onClick={onNavigate}
                      // Active link: a light gold background and a gold bar on its left edge
                      className={`relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${active ? 'bg-gold/10 font-semibold text-white before:absolute before:inset-y-1.5 before:left-0 before:w-1 before:rounded-full before:bg-gold' : 'text-stone-300 hover:bg-white/5 hover:text-white'}`}
                    >
                      <Icon name={n.icon} className={`h-[18px] w-[18px] shrink-0 ${active ? 'text-gold' : 'text-stone-500'}`} />
                      <span className="flex-1 truncate">{n.label}</span>
                      {count > 0 && (
                        <span className="min-w-[20px] rounded-full bg-gold px-1.5 text-center text-[11px] font-bold leading-5 text-ink">
                          {count > 99 ? '99+' : count}
                          <span className="sr-only"> waiting</span>
                        </span>
                      )}
                      {n.soon && <span className="text-[10px] text-stone-500">soon</span>}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
      {custom && (
        <button type="button" onClick={resetOrder} className="mt-2 w-full rounded px-3 py-1 text-left text-xs text-stone-500 underline hover:text-stone-300">
          Reset order
        </button>
      )}
      <p aria-live="polite" className="sr-only">{said}</p>
    </nav>
  );
}
