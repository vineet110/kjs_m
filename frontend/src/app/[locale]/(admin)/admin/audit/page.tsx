'use client';
import { useEffect, useState } from 'react';
import { api, ApiFailure } from '@/lib/api';

type Row = { id: number; at: string; actor_label: string; action: string; entity_type: string; entity_id: string | null; after: Record<string, unknown> | null };

export default function AuditPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api<Row[]>('/admin/audit?limit=200').then(setRows).catch((e) => setError(e instanceof ApiFailure ? e.message : 'Could not load.'));
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Audit log</h1>
        <p className="text-sm text-slate-500">Who changed what, and when. Entries can't be edited or deleted (enforced by the database).</p>
      </div>
      {error && <p className="card p-4 text-sm text-red-700">{error}</p>}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="p-3">When (IST)</th><th className="p-3">Who</th><th className="p-3">Action</th><th className="p-3">Details</th></tr>
          </thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.id} className="border-t align-top">
                <td className="whitespace-nowrap p-3">{new Date(r.at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}</td>
                <td className="p-3">{r.actor_label}</td>
                <td className="p-3 font-medium">{r.action}</td>
                <td className="p-3 font-mono text-xs text-slate-500">{r.entity_type} #{r.entity_id} {r.after ? JSON.stringify(r.after) : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
