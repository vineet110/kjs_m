'use client';
// A board's History tab (order boards PR 3): who changed what and when, newest first, grouped by day
// (India time). Read only: the lines come from the audit log, which nobody can edit or delete.
import { useCallback, useEffect, useState } from 'react';
import { api, ApiFailure, type BoardHistory as History, type BoardHistoryItem } from '@/lib/api';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

/** The colour dot in front of a line: what kind of change it was. */
function dot(action: string): string {
  if (action.startsWith('file.delete')) return 'bg-red-500';
  if (action.startsWith('file.')) return 'bg-sky-500';
  if (action.includes('person') || action.includes('people')) return 'bg-violet-500';
  if (action === 'board.step_done' || action === 'board.finished') return 'bg-emerald-500';
  if (action === 'board.created') return 'bg-gold';
  return 'bg-slate-400';
}

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' });
const time = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' });

/** `version` changes whenever the board changes, so the newest lines are fetched again. */
export default function BoardHistory({ code, version }: { code: string; version: unknown }) {
  const [items, setItems] = useState<BoardHistoryItem[] | null>(null);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  // Another board: start again (don't show the old board's lines meanwhile)
  useEffect(() => {
    setItems(null);
    setMore(false);
  }, [code]);

  const load = useCallback(async (beforeId?: number) => {
    setBusy(true);
    setErr('');
    try {
      const h = await api<History>(`/boards/${code}/history${beforeId ? `?before_id=${beforeId}` : ''}`);
      // Answers are merged by line id (newest first), never swapped in: so a refresh after a change
      // keeps the older pages already shown, and answers that arrive out of order can't drop or repeat lines.
      let first = false;
      setItems((old) => {
        first = !old?.length;
        const byId = new Map([...(old ?? []), ...h.items].map((i) => [i.id, i]));
        return [...byId.values()].sort((x, y) => y.id - x.id);
      });
      if (beforeId || first) setMore(h.more); // "older lines exist" comes from the oldest page
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not load the history.');
    } finally {
      setBusy(false);
    }
  }, [code]);
  useEffect(() => {
    load();
  }, [load, version]);

  if (items === null) return err ? <LoadError error={err} onRetry={() => load()} /> : <Loading />;

  // Group the lines by day, keeping the newest-first order
  const groups: { day: string; lines: BoardHistoryItem[] }[] = []; // the same day can come twice (rare): keyed by its first line
  for (const i of items) {
    const d = day(i.at);
    if (groups.at(-1)?.day !== d) groups.push({ day: d, lines: [] });
    groups.at(-1)!.lines.push(i);
  }

  return (
    <section className="space-y-4">
      <p className="text-sm text-slate-500">Every change on this board, newest first. Nobody can edit or delete these lines.</p>
      {items.length === 0 && <p className="card p-6 text-sm text-slate-500">Nothing has happened on this board yet.</p>}
      {groups.map((g) => (
        <div key={g.lines[0].id} className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{g.day}</h3>
          <ol className="card divide-y">
            {g.lines.map((i) => (
              <li key={i.id} className="flex items-start gap-3 p-3 text-sm">
                <span aria-hidden className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${dot(i.action)}`} />
                <p className="min-w-0 flex-1"><b>{i.who}</b> {i.text}</p>
                <time dateTime={i.at} className="shrink-0 text-xs text-slate-500">{time(i.at)}</time>
              </li>
            ))}
          </ol>
        </div>
      ))}
      {err && <p className="text-sm text-red-700">{err}</p>}
      {more && (
        <button onClick={() => load(items.at(-1)?.id)} disabled={busy} className="btn-ghost py-1 disabled:opacity-50">
          {busy ? 'Loading…' : 'Show older'}
        </button>
      )}
    </section>
  );
}
