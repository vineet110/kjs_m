'use client';
// Reports: two tabs. Website insights (opens first) and Business (leads, attendance, tasks, boards).
// Each tab shows only for someone who may see it: Website insights needs insights.view and the site_insights
// area on (config/modules.ini); Business needs staff.approve. The API checks the same rules.
import { useState } from 'react';
import { useMe } from '@/components/portal/PortalShell';
import BusinessReport from '@/components/portal/reports/BusinessReport';
import WebsiteInsights from '@/components/portal/reports/WebsiteInsights';
import { PageTitle } from '@/components/portal/ui';
import { canSee } from '@/lib/modules';

type Tab = 'website' | 'business';

export default function Reports() {
  const me = useMe();
  const tabs: [Tab, string][] = [];
  if (me.permissions.includes('insights.view') && canSee(me, 'site_insights')) tabs.push(['website', 'Website insights']);
  if (me.permissions.includes('staff.approve')) tabs.push(['business', 'Business']);
  const [picked, setPicked] = useState<Tab | null>(null);
  const tab = tabs.find(([t]) => t === picked)?.[0] ?? tabs[0]?.[0]; // the first allowed tab until one is picked

  return (
    <div className="space-y-6">
      <PageTitle title="Reports" />
      {tabs.length > 1 && (
        <div role="tablist" aria-label="Reports" className="flex gap-1 overflow-x-auto overflow-y-hidden border-b">
          {tabs.map(([t, label]) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setPicked(t)}
              className={`-mb-px shrink-0 border-b-2 px-4 py-2 text-sm font-semibold ${tab === t ? 'border-gold text-ink' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
              {label}
            </button>
          ))}
        </div>
      )}
      {tab === 'website' && <WebsiteInsights />}
      {tab === 'business' && <BusinessReport />}
      {!tab && <p className="text-sm text-slate-500">You don&apos;t have access to any report.</p>}
    </div>
  );
}
