'use client';
// The portal's one "anything new?" check (GET /employee/updates). Every UPDATE_EVERY_MS while the tab is in
// front, and at once when you come back to the tab or after your own action (pokeUpdates()). It returns
// counters only: unread notifications, things waiting for approval, unread chat messages, new leads. Each part
// of the page (bell, sidebar badges, approvals, chat, lead lists) reloads itself only when ITS number changed,
// so nothing reloads every 30 s and a half-typed form is never disturbed.
// One check per tab, shared by everything on the page (not one timer per component). Updates show 0-30 s
// late; server push over the live connection makes them instant later (next task).
import { useEffect, useRef, useSyncExternalStore } from 'react';
import { api } from './api';

export type Updates = {
  notifications: number;
  approvals: number | null; // null = nothing for you to approve
  chat: number | null; // null = Chat switched off for you
  // New leads you can see (badges), and `changed`: when any lead last changed or got a note (lists reload on
  // it, since one lead leaving "new" while another arrives keeps every count the same). null = no leads.view
  leads: { all: number; koko: number; internal: number; changed: string | null } | null;
};

export const UPDATE_EVERY_MS = 30_000;

type Env = {
  fetch: () => Promise<Updates>;
  isVisible: () => boolean;
  setInterval: (fn: () => void, ms: number) => unknown;
  clearInterval: (t: unknown) => void;
};

/** The shared check. Exported for tests; the page uses the hooks below. */
export function createUpdatesStore(env: Env, every = UPDATE_EVERY_MS) {
  let value: Updates | null = null;
  let timer: unknown = null;
  let latest = 0;
  const listeners = new Set<() => void>();

  const set = (next: Updates | null) => {
    if (JSON.stringify(next) === JSON.stringify(value)) return; // same numbers: nobody reloads
    value = next;
    listeners.forEach((fn) => fn());
  };

  /** Asks now. Only the newest answer counts (a slow older one can't put an old number back). */
  function check() {
    const mine = ++latest;
    return env.fetch().then((r) => { if (mine === latest) set(r); }, () => undefined); // a failed check changes nothing
  }

  const tick = () => { if (env.isVisible()) check(); };

  return {
    get: () => value,
    check,
    /** Coming back to the tab: ask at once instead of waiting for the next tick. */
    onVisible: () => { if (env.isVisible()) check(); },
    /** Another account (log out / log in): forget the old numbers. */
    reset: () => { latest++; set(null); },
    subscribe(fn: () => void) {
      listeners.add(fn);
      if (listeners.size === 1) {
        check();
        timer = env.setInterval(tick, every);
      }
      return () => {
        listeners.delete(fn);
        if (listeners.size === 0 && timer !== null) {
          env.clearInterval(timer);
          timer = null;
        }
      };
    },
  };
}

// ----- The one store of this tab -----
let store: ReturnType<typeof createUpdatesStore> | null = null;
let storeFor: number | null = null; // the account the numbers belong to

function theStore() {
  if (!store) {
    store = createUpdatesStore({
      fetch: () => api<Updates>('/employee/updates'),
      isVisible: () => document.visibilityState === 'visible',
      setInterval: (fn, ms) => window.setInterval(fn, ms),
      clearInterval: (t) => window.clearInterval(t as number),
    });
    document.addEventListener('visibilitychange', () => store?.onVisible());
  }
  return store;
}

/** Check now, e.g. right after you approved someone or read a chat, so your own badges update at once.
 *  Resolves when the new numbers are in. */
export function pokeUpdates(): Promise<void> {
  return store?.check() ?? Promise.resolve();
}

/** The latest counters for this account (null until the first answer). */
export function useUpdates(accountId: number): Updates | null {
  const s = theStore();
  // Another account on this tab: drop the old numbers and ask again (after drawing, never during it)
  useEffect(() => {
    if (storeFor === accountId) return;
    storeFor = accountId;
    s.reset();
    s.check();
  }, [accountId, s]);
  const v = useSyncExternalStore(s.subscribe, s.get, () => null);
  return storeFor === accountId ? v : null;
}

/** Runs `onChange` when the picked number changes (not on the first answer: the page has just loaded it). */
export function useOnUpdate<T>(accountId: number, pick: (u: Updates) => T, onChange: () => void) {
  const u = useUpdates(accountId);
  const key = u ? JSON.stringify(pick(u)) : null;
  const prev = useRef<string | null>(null);
  const fn = useRef(onChange);
  fn.current = onChange;
  useEffect(() => {
    if (key === null) return;
    if (prev.current !== null && prev.current !== key) fn.current();
    prev.current = key;
  }, [key]);
}
