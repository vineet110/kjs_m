'use client';
// Complaints: bugs, issues and suggestions staff sent with "Report a problem". Newest first.
import { useCallback, useEffect, useState } from 'react';
import { EmptyState, fmtIST, PageTitle, Pill } from '@/components/portal/ui';
import { api } from '@/lib/api';
import { downloadUrl } from '@/lib/preview';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

type Complaint = {
  id: number; kind: string; title: string; description: string; page_path: string;
  created_at: string; created_by_name: string; files: { id: number; name: string }[];
};

export default function ComplaintsPage() {
  const [rows, setRows] = useState<Complaint[] | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const load = useCallback(() => {
    setLoadErr(null);
    api<Complaint[]>('/complaints').then(setRows).catch(setLoadErr);
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  if (loadErr) return <LoadError error={loadErr} onRetry={load} />;
  if (!rows) return <Loading />;
  return (
    <div className="space-y-6">
      <PageTitle title="Complaints" sub="Bugs, issues and suggestions sent with “Report a problem”. Newest first." />
      {rows.length === 0 ? <EmptyState title="No complaints yet" tone="done" /> : (
        <div className="card divide-y">
          {rows.map((c) => (
            <article key={c.id} className="space-y-1 p-4 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Pill value={c.kind} />
                <h2 className="font-semibold">{c.title}</h2>
              </div>
              <p className="whitespace-pre-wrap text-slate-700">{c.description}</p>
              <p className="text-xs text-slate-500">
                {c.created_by_name || 'Someone'} · {fmtIST(c.created_at)} · page <span className="font-mono">{c.page_path}</span>
              </p>
              {c.files.length > 0 && (
                <p className="text-xs">
                  {c.files.map((f) => (
                    <a key={f.id} href={downloadUrl(f.id)} className="mr-3 underline">{f.name}</a>
                  ))}
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
