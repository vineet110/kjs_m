'use client';
// Lead Management > Contacts: one row per person who sent us enquiries (website forms, Koko, internal).
// Same page for admin and staff: leads.view_all sees everyone, others their own + unassigned enquiries.
// "Opportunities" = enquiries: active = new or contacted, in-active = closed. Converted value: not tracked yet.
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import DataTable from '@/components/portal/DataTable';
import { PageTitle } from '@/components/portal/ui';
import { api, type Contact } from '@/lib/api';
import { useMe } from '@/components/portal/PortalShell';
import { useOnUpdate } from '@/lib/updates';
import LoadError from '@/components/ui/LoadError';

export default function ContactsPage() {
  const [rows, setRows] = useState<Contact[] | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const latest = useRef(0); // only the newest answer counts
  const load = useCallback(() => {
    const mine = ++latest.current;
    setLoadErr(null);
    api<Contact[]>('/employee/contacts')
      .then((r) => { if (mine === latest.current) setRows(r); })
      .catch((e) => { if (mine === latest.current) setLoadErr(e); });
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  useOnUpdate(useMe().id, (u) => u.leads?.changed, load); // a lead changed or arrived: reload

  return (
    <div className="space-y-5">
      <PageTitle title="Leads" sub="Everyone who sent us an enquiry. Open a name to work on it." />
      {loadErr ? <LoadError error={loadErr} onRetry={load} /> : <DataTable
        rows={rows}
        rowKey={(c) => c.lead_id}
        noun="Contacts"
        search={(c) => `${c.name} ${c.email} ${c.phone}`}
        empty={{ title: 'No contacts yet', text: 'A contact appears as soon as a visitor sends an enquiry or talks to Koko.' }}
        columns={[
          { label: 'Name', cell: (c) => <Link href={`/employee/contacts/${c.lead_id}`} className="font-medium text-sky-700 hover:underline">{c.name}</Link> },
          { label: 'Email', className: 'max-w-[14rem] truncate', cell: (c) => c.email || '—' },
          { label: 'Phone No', className: 'whitespace-nowrap', cell: (c) => c.phone || '—' },
          { label: 'Converted Value', cell: () => <span className="text-slate-400" title="Deal values are not recorded yet">—</span> },
          { label: 'Active Opportunities', className: 'text-center', cell: (c) => c.active },
          { label: 'In-Active Opportunities', className: 'text-center', cell: (c) => c.inactive },
          { label: 'Total', className: 'text-center font-semibold', cell: (c) => c.total },
        ]}
        actions={(c) => [
          { label: 'Open', href: `/employee/contacts/${c.lead_id}` },
          ...(c.phone ? [{ label: 'Call', href: `tel:${c.phone.replace(/\s/g, '')}` }] : []),
          ...(c.email ? [{ label: 'Email', href: `mailto:${c.email}` }] : []),
        ]}
      />}
    </div>
  );
}
