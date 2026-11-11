'use client';
// The bell: unread count, latest notifications, "mark all read". Checks every minute.
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type Notice } from '@/lib/api';
import { fmtIST } from './ui';

export default function Bell() {
  const [data, setData] = useState<{ unread: number; items: Notice[] }>({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    api<{ unread: number; items: Notice[] }>('/employee/notifications').then(setData).catch(() => undefined);
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);
  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  async function readAll() {
    await api('/employee/notifications/read', { method: 'POST', body: {} });
    load();
  }

  // Opening one notification marks it read, so the red count goes down without "Mark all read".
  // The count drops at once; the server is told in the background (if that fails, the next check brings it back).
  function readOne(n: Notice) {
    setOpen(false);
    if (n.read) return;
    setData((d) => ({ unread: Math.max(0, d.unread - 1), items: d.items.map((x) => (x.id === n.id ? { ...x, read: true } : x)) }));
    api('/employee/notifications/read', { method: 'POST', body: { ids: [n.id] } }).then(load, load);
  }

  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen(!open)} aria-label={`Notifications, ${data.unread} unread`} className="relative rounded-full p-2 hover:bg-slate-100">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {data.unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 min-w-[18px] rounded-full bg-red-600 px-1 text-center text-[11px] font-bold text-white">
            {data.unread > 99 ? '99+' : data.unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border bg-white shadow-xl">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-semibold">Notifications</span>
            {data.unread > 0 && <button onClick={readAll} className="text-xs underline">Mark all read</button>}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {data.items.length === 0 && <p className="p-4 text-sm text-slate-500">Nothing yet.</p>}
            {data.items.map((n) => (
              <Link key={n.id} href={n.link || '#'} onClick={() => readOne(n)} className={`block border-b px-3 py-2 text-sm hover:bg-slate-50 ${n.read ? 'text-slate-500' : ''}`}>
                <p className={n.read ? '' : 'font-semibold'}>{n.title}</p>
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
