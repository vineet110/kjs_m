'use client';
// Auto-assign: import buyer lists, choose each person's categories, preview, run now.
// Settings (batch size, max per day, hours) live in config/assign.ini.
import { useCallback, useEffect, useState } from 'react';
import { Msg, PageTitle, Pill } from '@/components/portal/ui';
import { api, ApiFailure, upload, type Category } from '@/lib/api';
import Loading from '@/components/ui/Loading';

type StaffRow = {
  user_id: number; name: string; categories: string[]; is_available: boolean; checked_in: boolean;
  batches_today: number; open_batch: { size: number; done: number } | null;
};
type Overview = {
  settings: { batch_size: number; max_batches_per_day: number; work_start: string; work_end: string };
  in_hours: boolean; unassigned: Record<string, number>; staff: StaffRow[];
  lists: { id: number; name: string; rows: number; created_at: string }[];
};
type Plan = { user_id: number; name: string; would_get: number; batches_today: number }[];

export default function AutoAssign() {
  const [o, setO] = useState<Overview | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    api<Overview>('/assign/overview').then(setO);
    setPlan(null);
  }, []);
  useEffect(() => {
    load();
    api<Category[]>('/public/categories').then(setCats);
  }, [load]);

  async function importFile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    try {
      const r = await upload<{ added: number; skipped_count: number; skipped: { row: number; reason: string }[] }>('/assign/import', new FormData(form));
      const why = r.skipped.slice(0, 5).map((s) => `row ${s.row}: ${s.reason}`).join('; ');
      setMsg({ ok: true, text: `Imported ${r.added} records.${r.skipped_count ? ` Skipped ${r.skipped_count} (${why}${r.skipped_count > 5 ? '…' : ''}).` : ''}` });
      form.reset();
      load();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Import failed.' });
    }
  }

  async function toggleCat(row: StaffRow, slug: string) {
    const next = row.categories.includes(slug) ? row.categories.filter((c) => c !== slug) : [...row.categories, slug];
    await api(`/assign/staff/${row.user_id}/categories`, { method: 'POST', body: { categories: next } });
    load();
  }

  async function runNow() {
    const r = await api<{ batches: number; given: { name: string; records: number }[] }>('/assign/run', { method: 'POST' });
    setMsg({ ok: true, text: r.batches ? `Gave ${r.given.map((g) => `${g.records} to ${g.name}`).join(', ')}.` : 'Nobody could get a batch right now (see the rules above).' });
    load();
  }

  if (!o) return <Loading />;
  const s = o.settings;

  return (
    <div className="space-y-6">
      <PageTitle
        title="Auto-assign"
        sub={`Batches of ${s.batch_size} records, max ${s.max_batches_per_day} per person per day, ${s.work_start}–${s.work_end} IST. Only to people who are checked in, receiving tasks, and have categories. (Edit config/assign.ini to change.)`}
      >
        <div className="flex gap-2">
          <button onClick={() => api<Plan>('/assign/preview').then(setPlan)} className="btn-ghost">Preview</button>
          <button onClick={runNow} className="btn-dark">Run now</button>
        </div>
      </PageTitle>
      <Msg msg={msg} />

      {plan && (
        <div className="card p-4 text-sm">
          <p className="mb-2 font-semibold">If we ran now:</p>
          {plan.length === 0 ? <p className="text-slate-500">Nobody is eligible right now.</p> : (
            <ul className="list-inside list-disc">{plan.map((p) => <li key={p.user_id}>{p.name}: {p.would_get} records (batch {p.batches_today + 1} today)</li>)}</ul>
          )}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-4">
        {cats.map((c) => (
          <div key={c.slug} className="card p-3">
            <p className="text-xs font-semibold uppercase text-slate-500">{c.name}</p>
            <p className="text-2xl font-bold">{o.unassigned[c.slug] ?? 0}</p>
            <p className="text-xs text-slate-500">records waiting</p>
          </div>
        ))}
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">Staff and their categories</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="p-3">Name</th><th className="p-3">Categories (click to switch)</th><th className="p-3">Now</th><th className="p-3">Today</th><th className="p-3">Open batch</th></tr>
            </thead>
            <tbody>
              {o.staff.map((r) => (
                <tr key={r.user_id} className="border-t">
                  <td className="p-3 font-medium">{r.name}</td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-1">
                      {cats.map((c) => (
                        <button key={c.slug} onClick={() => toggleCat(r, c.slug)}
                          className={`rounded-full px-2 py-0.5 text-xs ${r.categories.includes(c.slug) ? 'bg-forest text-white' : 'bg-white text-slate-500 ring-1 ring-slate-200'}`}>
                          {c.name}
                        </button>
                      ))}
                    </div>
                  </td>
                  <td className="p-3 space-x-1">
                    <Pill value={r.checked_in ? 'present' : 'off'} label={r.checked_in ? 'checked in' : 'not in'} />
                    <Pill value={r.is_available ? 'ok' : 'off'} label={r.is_available ? 'receiving' : 'paused'} />
                  </td>
                  <td className="p-3">{r.batches_today} / {s.max_batches_per_day}</td>
                  <td className="p-3">{r.open_batch ? `${r.open_batch.done} of ${r.open_batch.size} done` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">Import buyer records</h2>
        <form onSubmit={importFile} className="card flex flex-wrap items-end gap-3 p-4">
          <div><label className="label">Excel (.xlsx) or CSV</label><input type="file" name="file" accept=".xlsx,.csv" required className="input" /></div>
          <div><label className="label">Category if the file has none</label>
            <select name="default_category" className="input"><option value="">— use the file&apos;s column —</option>{cats.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}</select>
          </div>
          <button className="btn-dark">Import</button>
          <p className="w-full text-xs text-slate-500">First row = headers. Needs a <b>Company</b> column. Also read: Contact, Email, Phone, Country, Website, Category, Notes.</p>
        </form>
        {o.lists.length > 0 && (
          <div className="card divide-y text-sm">
            {o.lists.map((l) => <div key={l.id} className="flex justify-between p-3"><span>{l.name}</span><span className="text-slate-500">{l.rows} records</span></div>)}
          </div>
        )}
      </section>
    </div>
  );
}
