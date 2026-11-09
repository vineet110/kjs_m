'use client';
// The lead lists under Lead Management (Koko Lead, Internal lead): every lead from one source, in the same
// table as Contacts. A name opens the contact page. leads.view_all sees everyone's, others own + unassigned.
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api, type Lead } from '@/lib/api';
import LoadError from '@/components/ui/LoadError';
import DataTable from './DataTable';
import { useMe } from './PortalShell';
import { fmtIST, Pill } from './ui';

export function useSourceLeads(source: string) {
  const me = useMe();
  const all = me.permissions.includes('leads.view_all');
  const [rows, setRows] = useState<Lead[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => {
    setError(null);
    api<Lead[]>(`${all ? '/admin/leads' : '/employee/leads'}?source=${source}`).then(setRows).catch(setError);
  }, [all, source]);
  useEffect(() => {
    load();
  }, [load]);
  return { rows, reload: load, error };
}

/** error / onRetry: from useSourceLeads; a failed load shows "Try again", not an empty list. */
export default function LeadSourceList({ rows, empty, error, onRetry }: {
  rows: Lead[] | null; empty: { title: string; text?: string }; error?: unknown; onRetry?: () => void;
}) {
  if (error && onRetry) return <LoadError error={error} onRetry={onRetry} />;
  return (
    <DataTable
      rows={rows}
      rowKey={(l) => l.id}
      noun="Leads"
      search={(l) => `${l.name} ${l.company} ${l.email} ${l.phone} ${l.product_name ?? ''} ${l.category_name ?? ''}`}
      empty={empty}
      columns={[
        { label: 'Name', cell: (l) => (
          <span>
            <Link href={`/employee/contacts/${l.id}`} className="font-medium text-sky-700 hover:underline">{l.name}</Link>
            {l.company && <span className="block text-xs text-slate-500">{l.company}</span>}
          </span>
        ) },
        { label: 'Email', className: 'max-w-[14rem] truncate', cell: (l) => l.email || '—' },
        { label: 'Phone No', className: 'whitespace-nowrap', cell: (l) => l.phone || '—' },
        { label: 'Interested in', cell: (l) => l.product_name || l.category_name || '—' },
        { label: 'Status', cell: (l) => <Pill value={l.status} /> },
        { label: 'Owner', cell: (l) => l.owner_name || <span className="text-slate-400">Unassigned</span> },
        { label: 'Received', className: 'whitespace-nowrap text-slate-500', cell: (l) => fmtIST(l.created_at) },
      ]}
      actions={(l) => [
        { label: 'Open', href: `/employee/contacts/${l.id}` },
        ...(l.phone ? [{ label: 'Call', href: `tel:${l.phone.replace(/\s/g, '')}` }] : []),
        ...(l.email ? [{ label: 'Email', href: `mailto:${l.email}` }] : []),
      ]}
    />
  );
}
