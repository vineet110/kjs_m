'use client';
// Reports > Website insights: what website visitors view, search and click (backend site_insights_service).
// Real numbers only (D6): an empty table shows zeros. Ranges and list sizes come from config/site_insights.ini.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Bars, Columns, Panel } from '@/components/portal/charts';
import { fmtDay } from '@/components/portal/ui';
import { api, ApiFailure } from '@/lib/api';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

type Data = {
  days: number; default_days: number; day_choices: number[]; keep_days: number;
  totals: { visits: number; page_views: number; product_views: number; searches: number; searches_no_results: number; enquiries_sent: number };
  per_day: { day: string; visits: number; views: number }[];
  top_products: { slug: string; name: string; views: number; visits: number }[];
  top_pages: { path: string; views: number }[];
  top_searches: { query: string; count: number; results: number | null }[];
  no_results: { query: string; count: number }[];
  buttons: { button: string; clicks: number }[];
  sources: { source: string; visits: number }[];
  devices: Record<string, number>;
};

// Names people read for the button names in config/site_insights.ini (an unknown name is shown as it is)
const BUTTON: Record<string, string> = {
  add_to_enquiry: 'Add to enquiry', spec_sheet: 'Spec sheet', price_sheet: 'Price sheet', whatsapp: 'WhatsApp',
  call: 'Call', send_enquiry: 'Enquiry sent', configurator: 'Configurator', sample_quote: 'Sample / quote',
};
const DEVICE: Record<string, string> = { mobile: 'Mobile', tablet: 'Tablet', desktop: 'Computer' };

export default function WebsiteInsights() {
  const [days, setDays] = useState<number | null>(null); // null = the default range (site_insights.ini)
  const [d, setD] = useState<Data | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const latest = useRef(0); // only the newest request's answer is shown (a slow older one is ignored)
  const load = useCallback(() => {
    const id = ++latest.current;
    setLoadErr(null);
    api<Data>(`/admin/site-insights${days ? `?days=${days}` : ''}`)
      .then((x) => id === latest.current && setD(x))
      .catch((err) => {
        if (id !== latest.current) return;
        // The range is longer than the days now kept (settings changed while the page was open): show the
        // default range instead of an error that "Try again" can't fix
        if (days && err instanceof ApiFailure && err.body.code === 'bad_range') setDays(null);
        else setLoadErr(err);
      });
  }, [days]);
  useEffect(() => {
    load();
  }, [load]);
  if (loadErr) return <LoadError error={loadErr} onRetry={load} />;
  if (!d) return <Loading />;

  const t = d.totals;
  const tiles = [
    { label: 'Visits', value: t.visits, sub: 'one visit = one browser tab' },
    { label: 'Pages viewed', value: t.page_views, sub: `${t.product_views} of them product pages` },
    { label: 'Searches', value: t.searches, sub: `${t.searches_no_results} found nothing` },
    { label: 'Enquiries sent', value: t.enquiries_sent, sub: 'from the website forms' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">
          No cookies or IP addresses. Phone numbers and emails typed into search are hidden. Staff and
          search-engine robots are not counted. Some visitors block trackers, so real numbers are a little higher.
        </p>
        <div className="flex gap-1" role="group" aria-label="Date range">
          {d.day_choices.filter((n) => n <= d.keep_days).map((n) => (
            <button key={n} onClick={() => setDays(n)} aria-pressed={d.days === n}
              className={`rounded-full border px-3 py-1 text-sm font-semibold ${d.days === n ? 'border-gold bg-gold/10 text-ink' : 'border-slate-200 text-slate-500 hover:text-slate-800'}`}>
              {n} days
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map((x) => (
          <div key={x.label} className="card p-4">
            <p className="text-xs font-semibold uppercase text-slate-500">{x.label}</p>
            <p className="mt-1 text-3xl font-bold">{x.value}</p>
            <p className="text-xs text-slate-500">{x.sub}</p>
          </div>
        ))}
      </div>

      <Panel title={`Visits per day, last ${d.days} days`}>
        <Columns data={d.per_day.map((x) => ({ label: fmtDay(x.day), value: x.visits }))} />
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Most viewed products">
          <Bars data={d.top_products.map((p) => ({ label: p.name, value: p.views }))} />
        </Panel>
        <Panel title="Top searches">
          <Bars data={d.top_searches.map((s) => ({ label: s.query, value: s.count }))} />
        </Panel>
        <Panel title="Searches that found nothing">
          <p className="-mt-2 text-xs text-slate-500">Products buyers looked for that the website doesn&apos;t show.</p>
          <Bars data={d.no_results.map((s) => ({ label: s.query, value: s.count }))} />
        </Panel>
        <Panel title="Most clicked buttons">
          <Bars data={d.buttons.map((b) => ({ label: BUTTON[b.button] ?? b.button, value: b.clicks }))} />
        </Panel>
        <Panel title="Where visitors came from">
          <Bars data={d.sources.map((s) => ({ label: s.source, value: s.visits }))} />
        </Panel>
        <Panel title="Mobile or computer (visits)">
          <Bars data={Object.entries(d.devices).map(([k, v]) => ({ label: DEVICE[k] ?? k, value: v }))} />
        </Panel>
        <Panel title="Most viewed pages">
          <Bars data={d.top_pages.map((p) => ({ label: p.path === 'other' ? 'Other pages' : p.path, value: p.views }))} />
        </Panel>
      </div>
    </div>
  );
}
