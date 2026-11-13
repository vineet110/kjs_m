'use client';
// Bulk import: each row of an Excel / CSV file becomes an internal lead (yours from the start).
// Step 1 reads and checks every row (nothing saved): rows with a problem can't be ticked, and people
// already in our leads or repeated in the file start unticked. Step 2 saves the ticked rows, all or none.
import { useRef, useState } from 'react';
import { api, ApiFailure, upload } from '@/lib/api';
import ExtraColumns, { extraColumns, pickExtra, type ExtraColumn, type ExtraDecision } from './ExtraColumns';
import { Msg } from './ui';

type Fields = Record<'name' | 'company' | 'email' | 'phone' | 'country' | 'buyer_type' | 'category_slug' | 'quantity' | 'message', string>;
type Row = { fields: Fields; extra: Record<string, string>; problems: string[]; duplicate: 'existing' | 'file' | null };

const DUPLICATE = { existing: 'Already in your leads', file: 'Repeated in this file' };

export default function ImportLeads({ onDone }: { onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [ticked, setTicked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState<'' | 'reading' | 'saving'>('');
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  // Columns we have no field for: asked once for the whole file (Add / Reject), then applied to every row
  const [cols, setCols] = useState<ExtraColumn[]>([]);
  const [decision, setDecision] = useState<ExtraDecision | null>(null);
  const [asking, setAsking] = useState(false);

  async function read(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy('reading');
    setMsg(null);
    setRows(null);
    try {
      const form = new FormData();
      form.set('file', file);
      const r = await upload<{ rows: Row[] }>('/employee/leads/import/preview', form);
      setRows(r.rows);
      const unknown = extraColumns(r.rows);
      setCols(unknown);
      setDecision(null);
      setAsking(unknown.length > 0);
      setTicked(new Set(r.rows.flatMap((row, i) => (row.problems.length || row.duplicate ? [] : [i]))));
    } catch (x) {
      setMsg({ ok: false, text: x instanceof ApiFailure ? x.message : 'Could not read the file.' });
    } finally {
      setBusy('');
      if (input.current) input.current.value = '';
    }
  }

  function toggle(i: number) {
    setTicked((now) => {
      const next = new Set(now);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  async function save() {
    if (!rows || !ticked.size) return;
    setBusy('saving');
    setMsg(null);
    try {
      const leads = [...ticked].sort((a, b) => a - b).map((i) => {
        const f = rows[i].fields;
        return { ...f, email: f.email || null, category_slug: f.category_slug || null, extra: pickExtra(rows[i].extra, decision) };
      });
      const r = await api<{ created: number }>('/employee/leads/import', {
        method: 'POST', body: { leads, extra_rejected: decision?.rejected ?? [] },
      });
      setRows(null);
      setTicked(new Set());
      setMsg({ ok: true, text: `${r.created} lead${r.created === 1 ? '' : 's'} imported. They are yours and show in the list below.` });
      onDone();
    } catch (x) {
      setMsg({ ok: false, text: x instanceof ApiFailure ? x.message : 'Could not import. Nothing was saved.' });
    } finally {
      setBusy('');
    }
  }

  const valid = rows?.filter((r) => !r.problems.length).length ?? 0;
  return (
    <div className="card space-y-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Import leads from Excel / CSV</h2>
          <p className="text-sm text-slate-500">First row = column names (Name, Phone, Company, Email…). Each row becomes a lead. Up to 500 rows.</p>
        </div>
        <label className={`btn-ghost cursor-pointer py-1 ${busy ? 'opacity-50' : ''}`}>
          {busy === 'reading' ? 'Reading…' : rows ? 'Choose another file' : 'Choose file'}
          <input ref={input} type="file" accept=".xlsx,.csv" className="sr-only" onChange={read} disabled={!!busy} />
        </label>
      </div>
      <Msg msg={msg} />
      {asking && <ExtraColumns columns={cols} onDone={(d) => { setDecision(d); setAsking(false); }} />}
      {rows && (
        <>
          {cols.length > 0 && decision && (
            <p className="text-sm text-slate-600">
              {decision.added.length > 0 && <><b>Extra Info</b> (saved with each lead): {decision.added.join(', ')}. </>}
              {decision.rejected.length > 0 && <><b>Not saved</b>: {decision.rejected.join(', ')}. </>}
              <button type="button" className="text-xs underline" onClick={() => setAsking(true)} disabled={!!busy}>Change</button>
            </p>
          )}
          <p className="text-sm text-slate-600">
            {rows.length} rows · {valid} can be imported · {ticked.size} ticked.
            {' '}Rows with a problem can&apos;t be ticked: fix them in the file and choose it again.
          </p>
          <div className="max-h-[28rem] overflow-auto rounded-lg border">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="sticky top-0 bg-slate-50 text-xs uppercase text-slate-500">
                <tr><th className="p-2"><span className="sr-only">Import</span></th><th className="p-2">Name</th><th className="p-2">Phone</th><th className="p-2">Company</th><th className="p-2">Email</th><th className="p-2">Check</th></tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((r, i) => (
                  <tr key={i} className={r.problems.length ? 'bg-red-50/50' : ''}>
                    <td className="p-2">
                      <input type="checkbox" aria-label={`Import row ${i + 2}`} checked={ticked.has(i)} disabled={!!r.problems.length || !!busy}
                        onChange={() => toggle(i)} />
                    </td>
                    <td className="p-2">{r.fields.name || <span className="text-slate-400">Not specified</span>}</td>
                    <td className="p-2">{r.fields.phone || <span className="text-slate-400">Not specified</span>}</td>
                    <td className="p-2">{r.fields.company || <span className="text-slate-400">Not specified</span>}</td>
                    <td className="p-2">{r.fields.email || <span className="text-slate-400">Not specified</span>}</td>
                    <td className="p-2 text-xs">
                      {r.problems.map((p) => <p key={p} className="text-red-700">{p}</p>)}
                      {r.duplicate && <p className="text-amber-700">{DUPLICATE[r.duplicate]}</p>}
                      {!r.problems.length && !r.duplicate && <span className="text-green-700">OK</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button type="button" className="btn-dark" disabled={!ticked.size || !!busy || asking} onClick={save}>
            {busy === 'saving' ? 'Importing…' : `Import ${ticked.size} lead${ticked.size === 1 ? '' : 's'}`}
          </button>
        </>
      )}
    </div>
  );
}
