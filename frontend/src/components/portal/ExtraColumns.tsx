'use client';
// "Extra Info" pop-up: a file has columns we have no field for (e.g. "GST No"). The person who read the file
// decides, one column at a time: Add (kept on the lead as Extra Info), Add all, Reject (not saved), Reject all.
// Nothing is saved here: the decisions go with the lead when it is saved, and the server writes them to the
// audit log.
import { useState } from 'react';

export const MAX_EXTRA = 30; // same limit as the server (schemas/lead.py)

export type ExtraColumn = { name: string; sample: string };
export type ExtraDecision = { added: string[]; rejected: string[] };

/** The file's unknown columns, each once, with the first value found (to show what it holds). */
export function extraColumns(rows: { extra: Record<string, string> }[]): ExtraColumn[] {
  const seen = new Map<string, string>();
  for (const r of rows) for (const [k, v] of Object.entries(r.extra)) if (!seen.get(k)) seen.set(k, v);
  return [...seen].map(([name, sample]) => ({ name, sample }));
}

/** Only the columns the person chose to Add. */
export function pickExtra(extra: Record<string, string>, decision: ExtraDecision | null): Record<string, string> {
  const added = new Set(decision?.added ?? []);
  return Object.fromEntries(Object.entries(extra).filter(([k]) => added.has(k)));
}

export default function ExtraColumns({ columns, onDone }: { columns: ExtraColumn[]; onDone: (d: ExtraDecision) => void }) {
  const [i, setI] = useState(0);
  const [added, setAdded] = useState<string[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const col = columns[i];
  const full = added.length >= MAX_EXTRA;

  function decide(add: boolean, all: boolean) {
    const names = all ? columns.slice(i).map((c) => c.name) : [col.name];
    let nextAdded = added;
    let nextRejected = rejected;
    if (add) {
      const room = MAX_EXTRA - added.length; // never more than the server takes; the rest are rejected
      nextAdded = [...added, ...names.slice(0, room)];
      nextRejected = [...rejected, ...names.slice(room)];
    } else {
      nextRejected = [...rejected, ...names];
    }
    const next = i + names.length;
    if (next >= columns.length) return onDone({ added: nextAdded, rejected: nextRejected });
    setAdded(nextAdded);
    setRejected(nextRejected);
    setI(next);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="extra-title" className="w-full max-w-md space-y-4 rounded-xl bg-white p-5 shadow-xl">
        <div>
          <p className="text-xs text-slate-500">New column {i + 1} of {columns.length}</p>
          <h2 id="extra-title" className="text-lg font-semibold">&quot;{col.name}&quot;</h2>
          <p className="text-sm text-slate-600">We have no field for this column. Keep it on the lead as <b>Extra Info</b>?</p>
        </div>
        {col.sample && (
          <p className="truncate rounded-lg bg-slate-50 px-3 py-2 text-sm"><span className="text-slate-500">Value: </span>{col.sample}</p>
        )}
        {full && <p className="text-sm text-amber-700">A lead can keep up to {MAX_EXTRA} Extra Info columns. The rest can only be rejected.</p>}
        <div className="grid grid-cols-2 gap-2">
          <button type="button" className="btn-dark" disabled={full} onClick={() => decide(true, false)}>Add</button>
          <button type="button" className="btn-ghost" disabled={full} onClick={() => decide(true, true)}>Add all ({columns.length - i})</button>
          <button type="button" className="btn-ghost" onClick={() => decide(false, false)}>Reject</button>
          <button type="button" className="btn-ghost" onClick={() => decide(false, true)}>Reject all ({columns.length - i})</button>
        </div>
        <p className="text-xs text-slate-500">Rejected columns are not saved. Want to keep one? Choose Add to save it in Extra Info.</p>
      </div>
    </div>
  );
}
