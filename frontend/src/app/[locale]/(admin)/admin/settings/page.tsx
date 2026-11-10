'use client';
// Settings: every tunable value, where it comes from (env var / ini file / built-in default)
// and which file to edit. Secrets are never shown (they live only in .env).
import { useCallback, useEffect, useState } from 'react';
import { useToast } from '@/components/portal/Toast';
import { PageTitle, Pill } from '@/components/portal/ui';
import { api, ApiFailure } from '@/lib/api';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

type Row = { key: string; value: unknown; default: unknown; source: 'env' | 'ini' | 'default'; file: string; env_var: string };

const show = (v: unknown) => (Array.isArray(v) ? v.join(', ') : typeof v === 'object' && v ? Object.entries(v).map(([k, x]) => `${k}=${x}`).join(', ') || '—' : String(v));

export default function SettingsPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [filter, setFilter] = useState('');
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const toast = useToast();
  const load = useCallback(() => {
    setLoadErr(null);
    api<Row[]>('/admin/config').then(setRows).catch(setLoadErr);
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function reload() {
    try {
      setRows(await api<Row[]>('/admin/config/reload', { method: 'POST', safeToRepeat: true }));
    } catch (e) {
      toast(e instanceof ApiFailure ? e.message : 'Could not reload. Please try again.', 'error');
    }
  }

  if (loadErr) return <LoadError error={loadErr} onRetry={load} />;
  if (!rows) return <Loading />;
  const shown = rows.filter((r) => r.key.includes(filter.toLowerCase()));
  const groups = Array.from(new Set(shown.map((r) => r.key.split('.')[0])));

  return (
    <div className="space-y-6">
      <PageTitle title="Manage settings" sub="To change a value, edit the file shown (on the server) and save. It applies within a few seconds, no restart.">
        <div className="flex gap-2">
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search, e.g. sla" className="input w-48" />
          <button onClick={reload} className="btn-ghost">Re-read files now</button>
        </div>
      </PageTitle>
      {groups.map((g) => (
        <section key={g} className="space-y-2">
          <h2 className="font-semibold">{g} <span className="text-xs font-normal text-slate-500">config/{g}.ini</span></h2>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <tbody>
                {shown.filter((r) => r.key.startsWith(`${g}.`)).map((r) => (
                  <tr key={r.key} className="border-t first:border-t-0">
                    <td className="w-1/3 p-2 font-mono text-xs">{r.key.split('.').slice(1).join('.')}</td>
                    <td className="p-2 font-medium">{show(r.value)}</td>
                    <td className="p-2"><Pill value={r.source === 'env' ? 'at_risk' : r.source === 'ini' ? 'ok' : 'off'} label={r.source === 'env' ? `env ${r.env_var}` : r.source} /></td>
                    <td className="p-2 text-xs text-slate-500">{r.source !== 'default' && show(r.value) !== show(r.default) ? `default ${show(r.default)}` : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
