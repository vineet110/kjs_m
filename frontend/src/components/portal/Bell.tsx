'use client';
// The bell: unread notifications only. Opening one marks it read and it leaves the list at once;
// "Mark all read" empties it. The count comes from the portal's 30-second check (lib/updates.ts); the list
// is fetched when you open the bell, and again when the count changes while it is open.
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type Notice } from '@/lib/api';
import { pokeUpdates, useOnUpdate, useUpdates } from '@/lib/updates';
import { fmtIST } from './ui';

export default function Bell({ meId }: { meId: number }) {
  const updates = useUpdates(meId);
  const [items, setItems] = useState<Notice[] | null>(null);
  const [hidden, setHidden] = useState<Set<number>>(new Set()); // opened here: kept out of the list
  const [pending, setPending] = useState<Set<number>>(new Set()); // opened here, the server's count doesn't know yet
  const [err, setErr] = useState('');
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const latest = useRef(0); // only the newest list answer counts (CodeRabbit on #76)
  const pendingNow = useRef(pending); // the latest `pending`, for answers that arrive later
  pendingNow.current = pending;
  const sent = useRef<Set<number>>(new Set()); // read saved on the server; waiting for a fresh count

  // A list asked for after a read leaves that notification out by itself, so it also clears `hidden`
  const load = useCallback(() => {
    const mine = ++latest.current;
    api<{ unread: number; items: Notice[] }>('/employee/notifications?unread=1')
      // A read still being saved may be in this answer: it stays hidden until the server has it
      .then((r) => { if (mine === latest.current) { setItems(r.items); setHidden(new Set(pendingNow.current)); } })
      .catch(() => undefined);
  }, []);
  useEffect(() => { if (open) load(); }, [open, load]);
  const seen = useRef(false); // the list was fetched at least once: keep it fresh when the count moves
  if (items !== null) seen.current = true;
  useOnUpdate(meId, (u) => u.notifications, () => { if (seen.current) load(); });
  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const shown = (items ?? []).filter((n) => !hidden.has(n.id));
  // Only reads the server's count doesn't include yet are taken off it
  const unread = Math.max(0, (updates?.notifications ?? 0) - pending.size);
  const without = (set: Set<number>, ids: number[]) => { const x = new Set(set); ids.forEach((i) => x.delete(i)); return x; };

  /** Marks these read: they leave the list and the count at once. Once the server has them and the count is
   *  fresh, they stop being subtracted. If it fails they come back, and the panel says so. */
  function markRead(ids: number[], body: { ids?: number[] }) {
    latest.current++; // a list asked for before this read could still contain them: ignore it
    setErr('');
    setHidden((h) => new Set([...h, ...ids]));
    setPending((p) => new Set([...p, ...ids]));
    api('/employee/notifications/read', { method: 'POST', body })
      .then(() => { ids.forEach((i) => sent.current.add(i)); return pokeUpdates(); })
      // Stop subtracting only once a fresh count is in; if this check failed, the next one does it (below)
      .then((fresh) => { if (fresh) { setPending((p) => without(p, ids)); ids.forEach((i) => sent.current.delete(i)); } }, () => {
        setHidden((h) => without(h, ids));
        setPending((p) => without(p, ids));
        setErr('Could not mark them as read. Please try again.');
      });
  }
  // A fresh count arrived (any check): reads already saved on the server are in it now
  useEffect(() => {
    if (!updates || sent.current.size === 0) return;
    const done = [...sent.current];
    sent.current.clear();
    setPending((p) => without(p, done));
  }, [updates]); // eslint-disable-line react-hooks/exhaustive-deps
  const readAll = () => markRead((items ?? []).map((n) => n.id), {});
  const readOne = (n: Notice) => { setOpen(false); markRead([n.id], { ids: [n.id] }); };

  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen(!open)} aria-label={`Notifications, ${unread} unread`} className="relative rounded-full p-2 hover:bg-slate-100">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 min-w-[18px] rounded-full bg-red-600 px-1 text-center text-[11px] font-bold text-white">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border bg-white shadow-xl">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-semibold">Notifications</span>
            {shown.length > 0 && <button onClick={readAll} className="text-xs underline">Mark all read</button>}
          </div>
          {err && <p role="alert" className="border-b bg-red-50 px-3 py-2 text-xs text-red-700">{err}</p>}
          <div className="max-h-96 overflow-y-auto">
            {items !== null && shown.length === 0 && <p className="p-4 text-sm text-slate-500">You&apos;re all caught up.</p>}
            {shown.map((n) => (
              <Link key={n.id} href={n.link || '#'} onClick={() => readOne(n)} className="block border-b px-3 py-2 text-sm hover:bg-slate-50">
                <p className="font-semibold">{n.title}</p>
                {n.body && <p className="line-clamp-2 text-xs text-slate-500">{n.body}</p>}
                <p className="text-[11px] text-slate-400">{fmtIST(n.created_at)}</p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
