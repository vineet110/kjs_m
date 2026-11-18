'use client';
// The lead lists under Lead Management (Koko Lead, Internal lead): every lead from one source, in the same
// table as Contacts. A name opens the contact page. leads.view_all sees everyone's, others own + unassigned.
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { leadPages, type Lead } from '@/lib/api';
import LoadError from '@/components/ui/LoadError';
import DataTable from './DataTable';
import { useMe } from './PortalShell';
import { useOnUpdate } from '@/lib/updates';
import { fmtIST, Pill } from './ui';

export function useSourceLeads(source: string) {
  const me = useMe();
  const all = me.permissions.includes('leads.view_all');
  const [rows, setRows] = useState<Lead[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const size = (all ? me.limits?.leads_page_admin : me.limits?.leads_page_employee) ?? (all ? 500 : 200);
  const [pages, setPages] = useState(1); // "Load more" adds a page
  const [more, setMore] = useState(false);
  const latest = useRef(0); // only the newest answer counts: an older, slower one can't put back an old list
  const load = useCallback(() => {
    const mine = ++latest.current;
    setError(null);
    leadPages(all ? '/admin/leads' : '/employee/leads', new URLSearchParams({ source }), pages, size)
      .then((r) => { if (mine === latest.current) { setRows(r.rows); setMore(r.full); } })
      .catch((e) => { if (mine === latest.current) setError(e); });
  }, [all, source, pages, size]);
  useEffect(() => {
    load();
  }, [load]);
  // A lead changed or arrived: reload when the portal's 30-second check says so
  useOnUpdate(me.id, (u) => u.leads?.changed, load);
  return { rows, reload: load, error, more, loadMore: () => setPages((n) => n + 1) };
}

/** error / onRetry: from useSourceLeads; a failed load shows "Try again", not an empty list.
 *  onMore: from useSourceLeads (loadMore, when `more`): a "Load more" button under the table. */
export default function LeadSourceList({ rows, empty, error, onRetry, onMore }: {
  rows: Lead[] | null; empty: { title: string; text?: string }; error?: unknown; onRetry?: () => void; onMore?: () => void;
}) {
  if (error && onRetry) return <LoadError error={error} onRetry={onRetry} />;
  return (
    <div className="space-y-3">
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
      {onMore && <button onClick={onMore} className="btn-ghost w-full">Load more (older leads)</button>}
    </div>
  );
}
