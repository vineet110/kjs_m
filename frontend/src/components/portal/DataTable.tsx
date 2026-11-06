'use client';
// The Lead Management table (Contacts, Koko leads, Internal leads): a search box, the table, "Showing 1 to 10
// of 114 Contacts", rows per page and Previous / 1 2 … / Next. Search and pages run in the browser: the
// lists are small (a few thousand rows at most), so there is nothing to ask the server again.
import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import Loading from '@/components/ui/Loading';
import { EmptyState } from './ui';
import { Icon } from './icons';

export type Column<T> = { label: string; cell: (row: T, n: number) => React.ReactNode; className?: string };
export type RowAction = { label: string; href?: string; onClick?: () => void };

const SIZES = [10, 25, 50];

export default function DataTable<T>({ rows, columns, rowKey, search, noun, actions, empty }: {
  rows: T[] | null;
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  search: (row: T) => string; // the text the search box looks in
  noun: string; // "Contacts", "Leads"
  actions?: (row: T) => RowAction[];
  empty: { title: string; text?: string };
}) {
  const [q, setQ] = useState('');
  const [size, setSize] = useState(10);
  const [page, setPage] = useState(1);

  const found = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return (rows ?? []).filter((r) => {
      const text = search(r).toLowerCase();
      return words.every((w) => text.includes(w));
    });
  }, [rows, q, search]);
  const pages = Math.max(1, Math.ceil(found.length / size));
  useEffect(() => setPage(1), [q, size]); // a new search starts on page 1
  const now = Math.min(page, pages); // the list got shorter (a row closed elsewhere): stay on a real page
  const shown = found.slice((now - 1) * size, now * size);
  const first = found.length ? (now - 1) * size + 1 : 0;

  return (
    <div className="space-y-3">
      <label className="relative block max-w-sm">
        <span className="sr-only">Search</span>
        <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="input rounded-full pl-9" />
      </label>

      {rows === null ? (
        <Loading />
      ) : found.length === 0 ? (
        <EmptyState title={q ? 'Nothing matches your search' : empty.title} text={q ? 'Try a name, email or phone number.' : empty.text} />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-sky-50/70 text-xs font-semibold text-slate-600">
              <tr>
                <th className="px-4 py-3">S.No</th>
                {columns.map((c) => <th key={c.label} className={`px-4 py-3 ${c.className ?? ''}`}>{c.label}</th>)}
                {actions && <th className="px-4 py-3 text-center">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {shown.map((r, i) => (
                <tr key={rowKey(r)} className="transition-colors hover:bg-amber-50/60">
                  <td className="px-4 py-3 text-slate-500">{first + i}</td>
                  {columns.map((c) => <td key={c.label} className={`px-4 py-3 ${c.className ?? ''}`}>{c.cell(r, first + i)}</td>)}
                  {actions && <td className="px-4 py-3 text-center"><Actions items={actions(r)} /></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rows !== null && found.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
          <p>Showing <b>{first}</b> to <b>{first + shown.length - 1}</b> of <b>{found.length}</b> {noun}</p>
          <div className="flex items-center gap-2">
            <label className="sr-only" htmlFor="rows-per-page">Rows per page</label>
            <select id="rows-per-page" value={size} onChange={(e) => setSize(Number(e.target.value))} className="input w-auto py-1">
              {SIZES.map((s) => <option key={s}>{s}</option>)}
            </select>
            <nav aria-label="Pages" className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1">
              <button type="button" disabled={now === 1} onClick={() => setPage(now - 1)} className="px-2 py-1 disabled:text-slate-300">‹ Previous</button>
              {pageList(now, pages).map((p, i) =>
                p === 0 ? (
                  <span key={`gap${i}`} className="px-1 text-slate-400">…</span>
                ) : (
                  <button key={p} type="button" onClick={() => setPage(p)} aria-current={p === now ? 'page' : undefined}
                    className={`min-w-[2rem] rounded-md px-2 py-1 ${p === now ? 'bg-orange-500 font-semibold text-white' : 'hover:bg-slate-100'}`}>
                    {p}
                  </button>
                ),
              )}
              <button type="button" disabled={now === pages} onClick={() => setPage(now + 1)} className="px-2 py-1 font-semibold disabled:font-normal disabled:text-slate-300">Next ›</button>
            </nav>
          </div>
        </div>
      )}
    </div>
  );
}

/** Page numbers to show: the first, the last, and the ones next to the current page; 0 = a "…" gap. */
function pageList(now: number, pages: number): number[] {
  const want = new Set([1, pages, now - 1, now, now + 1].filter((p) => p >= 1 && p <= pages));
  const out: number[] = [];
  [...want].sort((a, b) => a - b).forEach((p, i, all) => {
    if (i > 0 && p - all[i - 1] > 1) out.push(0);
    out.push(p);
  });
  return out;
}

/** The "•••" menu on a row. Closes on a click outside or Escape. */
function Actions({ items }: { items: RowAction[] }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);
  return (
    <div ref={box} className="relative inline-block">
      <button type="button" aria-label="Actions" aria-expanded={open} onClick={() => setOpen(!open)} className="rounded px-2 py-1 font-bold tracking-widest text-slate-600 hover:bg-slate-100">
        •••
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-40 rounded-lg border border-slate-200 bg-white py-1 text-left shadow-lg">
          {items.map((a) =>
            a.href?.startsWith('/') ? (
              <Link key={a.label} href={a.href} className="block px-3 py-1.5 hover:bg-slate-50">{a.label}</Link>
            ) : a.href ? ( // mailto: / tel:
              <a key={a.label} href={a.href} className="block px-3 py-1.5 hover:bg-slate-50">{a.label}</a>
            ) : (
              <button key={a.label} type="button" onClick={() => { setOpen(false); a.onClick?.(); }} className="block w-full px-3 py-1.5 text-left hover:bg-slate-50">{a.label}</button>
            ),
          )}
        </div>
      )}
    </div>
  );
}
