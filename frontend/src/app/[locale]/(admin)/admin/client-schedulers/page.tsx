'use client';
// Client Schedulers / Lead Harvester: automated background ingestion of buyer enquiries
// from APIs, Open Data files, RSS feeds, and Scraping into Record Lists for Auto-Assign.
// Compliant with India's DPDP Act: provenance tracking and terms confirmation.
import { useCallback, useEffect, useState } from 'react';
import { fmtIST, PageTitle, Pill } from '@/components/portal/ui';
import { api, ApiFailure } from '@/lib/api';
import Loading from '@/components/ui/Loading';

type SourceType = 'api' | 'open_data' | 'rss' | 'scrape';

type HarvestSource = {
  id: number;
  name: string;
  source_type: SourceType;
  url: string;
  auth_env_var: string;
  category: string;
  is_active: boolean;
  terms_checked: boolean;
  schedule_interval_minutes: number;
  last_run_at: string | null;
  last_status: string;
  created_at: string;
};

type HarvestRun = {
  id: number;
  source_id: number;
  source_name: string;
  source_type: string;
  status: string;
  found_count: number;
  accepted_count: number;
  dropped_count: number;
  drop_reasons: Record<string, number>;
  error_message: string;
  started_at: string;
  finished_at: string | null;
};

type HarvestStats = {
  total_sources: number;
  active_sources: number;
  total_runs: number;
  total_accepted: number;
  total_dropped: number;
};

const TYPE_LABELS: Record<SourceType, string> = {
  api: 'Official API',
  open_data: 'Open Data File (CSV/JSON)',
  rss: 'RSS / Tender Feed',
  scrape: 'Web Scraper',
};

const SCHEDULE_OPTIONS = [
  { label: 'Every 15 minutes', minutes: 15 },
  { label: 'Every 30 minutes', minutes: 30 },
  { label: 'Every hour', minutes: 60 },
  { label: 'Daily (24 hours)', minutes: 1440 },
  { label: 'Weekly (7 days)', minutes: 10080 },
];

export default function ClientSchedulersPage() {
  const [sources, setSources] = useState<HarvestSource[]>([]);
  const [runs, setRuns] = useState<HarvestRun[]>([]);
  const [stats, setStats] = useState<HarvestStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyRunId, setBusyRunId] = useState<number | null>(null);
  const [banner, setBanner] = useState<{ ok: boolean; text: string } | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingSource, setEditingSource] = useState<HarvestSource | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    source_type: 'api' as SourceType,
    url: '',
    auth_env_var: '',
    category: 'all',
    schedule_interval_minutes: 15,
    is_active: true,
    terms_checked: false,
  });

  const loadData = useCallback(async () => {
    try {
      const [srcList, runList, statData] = await Promise.all([
        api<HarvestSource[]>('/admin/harvest/sources'),
        api<HarvestRun[]>('/admin/harvest/runs?limit=30'),
        api<HarvestStats>('/admin/harvest/stats'),
      ]);
      setSources(srcList);
      setRuns(runList);
      setStats(statData);
    } catch (err) {
      setBanner({ ok: false, text: err instanceof ApiFailure ? err.message : 'Failed to load scheduler data.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  function openCreateModal() {
    setEditingSource(null);
    setFormData({
      name: '',
      source_type: 'api',
      url: '',
      auth_env_var: '',
      category: 'all',
      schedule_interval_minutes: 15,
      is_active: true,
      terms_checked: false,
    });
    setModalOpen(true);
  }

  function openEditModal(src: HarvestSource) {
    setEditingSource(src);
    setFormData({
      name: src.name,
      source_type: src.source_type,
      url: src.url,
      auth_env_var: src.auth_env_var,
      category: src.category,
      schedule_interval_minutes: src.schedule_interval_minutes,
      is_active: src.is_active,
      terms_checked: src.terms_checked,
    });
    setModalOpen(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editingSource) {
        await api(`/admin/harvest/sources/${editingSource.id}`, {
          method: 'PUT',
          body: formData,
        });
        setBanner({ ok: true, text: `Scheduler "${formData.name}" updated successfully.` });
      } else {
        await api('/admin/harvest/sources', {
          method: 'POST',
          body: formData,
        });
        setBanner({ ok: true, text: `Scheduler "${formData.name}" created successfully.` });
      }
      setModalOpen(false);
      loadData();
    } catch (err) {
      setBanner({ ok: false, text: err instanceof ApiFailure ? err.message : 'Save failed.' });
    }
  }

  async function toggleActive(src: HarvestSource) {
    try {
      if (src.source_type === 'scrape' && !src.is_active && !src.terms_checked) {
        setBanner({ ok: false, text: 'Scraping source requires terms to be checked before activation.' });
        return;
      }
      await api(`/admin/harvest/sources/${src.id}`, {
        method: 'PUT',
        body: { is_active: !src.is_active },
      });
      loadData();
    } catch (err) {
      setBanner({ ok: false, text: err instanceof ApiFailure ? err.message : 'Failed to toggle source.' });
    }
  }

  async function handleRunNow(src: HarvestSource) {
    setBusyRunId(src.id);
    setBanner(null);
    try {
      const res = await api<HarvestRun>(`/admin/harvest/sources/${src.id}/run`, { method: 'POST' });
      setBanner({
        ok: res.status === 'success' || res.status === 'partial',
        text: `Run finished for ${src.name}: ${res.accepted_count} accepted, ${res.dropped_count} dropped (${res.status}).`,
      });
      loadData();
    } catch (err) {
      setBanner({ ok: false, text: err instanceof ApiFailure ? err.message : 'Run trigger failed.' });
    } finally {
      setBusyRunId(null);
    }
  }

  async function handleDelete(src: HarvestSource) {
    if (!window.confirm(`Delete harvester scheduler "${src.name}"?`)) return;
    try {
      await api(`/admin/harvest/sources/${src.id}`, { method: 'DELETE' });
      setBanner({ ok: true, text: `Deleted scheduler "${src.name}".` });
      loadData();
    } catch (err) {
      setBanner({ ok: false, text: err instanceof ApiFailure ? err.message : 'Delete failed.' });
    }
  }

  if (loading) return <Loading />;

  return (
    <div className="space-y-6">
      <PageTitle
        title="Client Schedulers (Lead Harvester)"
        sub="Background ingestion of buyer enquiries from APIs, Open Data, RSS feeds, and Scraping into Record Lists for Auto-Assign."
      >
        <button
          onClick={openCreateModal}
          className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 shadow-sm transition"
        >
          + Add New Source
        </button>
      </PageTitle>

      {banner && (
        <div className={`rounded-lg p-3 text-sm flex justify-between items-center ${banner.ok ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-red-50 text-red-800 border border-red-200'}`}>
          <span>{banner.text}</span>
          <button onClick={() => setBanner(null)} className="text-xs font-bold px-2 py-0.5 ml-2 hover:opacity-75">✕</button>
        </div>
      )}

      {/* Metrics Row */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
            <div className="text-xs font-medium text-slate-500 uppercase">Active / Total</div>
            <div className="mt-1 text-2xl font-bold text-slate-900">{stats.active_sources} <span className="text-sm font-normal text-slate-400">/ {stats.total_sources}</span></div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
            <div className="text-xs font-medium text-slate-500 uppercase">Total Runs</div>
            <div className="mt-1 text-2xl font-bold text-slate-900">{stats.total_runs}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
            <div className="text-xs font-medium text-slate-500 uppercase">Leads Accepted</div>
            <div className="mt-1 text-2xl font-bold text-emerald-600">{stats.total_accepted}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
            <div className="text-xs font-medium text-slate-500 uppercase">Dropped (Filtered)</div>
            <div className="mt-1 text-2xl font-bold text-amber-600">{stats.total_dropped}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
            <div className="text-xs font-medium text-slate-500 uppercase">Quality Yield</div>
            <div className="mt-1 text-2xl font-bold text-slate-900">
              {stats.total_accepted + stats.total_dropped > 0
                ? `${Math.round((stats.total_accepted / (stats.total_accepted + stats.total_dropped)) * 100)}%`
                : '100%'}
            </div>
          </div>
        </div>
      )}

      {/* Harvester Sources Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        <div className="border-b border-slate-200 bg-slate-50/50 px-4 py-3 sm:px-6">
          <h2 className="text-sm font-bold text-slate-800">Configured Sources & Schedulers</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Source Name</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Target Category</th>
                <th className="px-4 py-3">Schedule</th>
                <th className="px-4 py-3">Last Run</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Active</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sources.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    No harvest sources configured yet. Click "+ Add New Source" to set up your first external enquiry scheduler.
                  </td>
                </tr>
              ) : (
                sources.map((src) => (
                  <tr key={src.id} className="hover:bg-slate-50/80 transition">
                    <td className="px-4 py-3 font-medium text-slate-900">
                      <div>{src.name}</div>
                      <div className="text-xs text-slate-400 truncate max-w-xs">{src.url}</div>
                      {src.auth_env_var && (
                        <div className="text-2xs text-slate-400 mt-0.5">Key: <code>${src.auth_env_var}</code></div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-block rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                        {src.source_type.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 capitalize text-slate-700">
                      {src.category}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">
                      Every {src.schedule_interval_minutes}m
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {src.last_run_at ? fmtIST(src.last_run_at) : 'Never'}
                    </td>
                    <td className="px-4 py-3">
                      <Pill value={src.last_status} />
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleActive(src)}
                        className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden ${src.is_active ? 'bg-emerald-600' : 'bg-slate-200'}`}
                      >
                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ease-in-out ${src.is_active ? 'translate-x-4' : 'translate-x-0'}`} />
                      </button>
                    </td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button
                        onClick={() => handleRunNow(src)}
                        disabled={busyRunId === src.id}
                        className="rounded bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-200 disabled:opacity-50 transition"
                      >
                        {busyRunId === src.id ? 'Running…' : 'Run now'}
                      </button>
                      <button
                        onClick={() => openEditModal(src)}
                        className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200 transition"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(src)}
                        className="rounded bg-rose-50 px-2 py-1 text-xs font-medium text-rose-600 hover:bg-rose-100 transition"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Run Audit Log */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        <div className="border-b border-slate-200 bg-slate-50/50 px-4 py-3 sm:px-6">
          <h2 className="text-sm font-bold text-slate-800">Recent Ingestion & Filter Runs (Audit Log)</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Found</th>
                <th className="px-4 py-3">Accepted</th>
                <th className="px-4 py-3">Dropped</th>
                <th className="px-4 py-3">Filter Reasons Breakdown</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-slate-400">
                    No run logs yet. Run a scheduler manually or wait for the background job to trigger.
                  </td>
                </tr>
              ) : (
                runs.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {fmtIST(r.started_at)}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800">
                      {r.source_name || `Source #${r.source_id}`}
                      <span className="ml-1.5 text-xs text-slate-400">({r.source_type})</span>
                    </td>
                    <td className="px-4 py-3">
                      <Pill value={r.status} />
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-700">
                      {r.found_count}
                    </td>
                    <td className="px-4 py-3 font-semibold text-emerald-600">
                      {r.accepted_count}
                    </td>
                    <td className="px-4 py-3 font-semibold text-amber-600">
                      {r.dropped_count}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {r.error_message && (
                        <div className="text-red-600 mb-1 font-medium">{r.error_message}</div>
                      )}
                      {Object.keys(r.drop_reasons).length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {Object.entries(r.drop_reasons).map(([reason, count]) => (
                            <span key={reason} className="rounded bg-slate-100 px-1.5 py-0.5 text-2xs text-slate-600 font-mono">
                              {reason}: {count}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Add / Edit Source */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-lg font-bold text-slate-900">
                {editingSource ? 'Edit Ingestion Scheduler' : 'Add New Lead Harvester Source'}
              </h3>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-slate-600 font-bold">✕</button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 text-sm">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">Source Name</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. IndiaMART Spices Directory"
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-slate-900 focus:border-emerald-500 focus:outline-hidden"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">Source Type</label>
                  <select
                    value={formData.source_type}
                    onChange={(e) => setFormData({ ...formData, source_type: e.target.value as SourceType })}
                    className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-slate-900 focus:border-emerald-500 focus:outline-hidden"
                  >
                    <option value="api">Official REST API</option>
                    <option value="open_data">Open Data File (CSV / JSON)</option>
                    <option value="rss">RSS / Tender Feed</option>
                    <option value="scrape">Web Scraping (Strict robots.txt)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">Target Category</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-slate-900 focus:border-emerald-500 focus:outline-hidden"
                  >
                    <option value="all">All (Coffee, Tea, Spices, Private Label)</option>
                    <option value="coffee">Coffee</option>
                    <option value="tea">Tea</option>
                    <option value="spices">Spices</option>
                    <option value="private_label">Private Label</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">Source URL / Endpoint</label>
                <input
                  type="url"
                  required
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  placeholder="https://api.indiamart.com/buyer-enquiries"
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-slate-900 focus:border-emerald-500 focus:outline-hidden"
                />
              </div>

              {formData.source_type === 'api' && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">Auth Env Variable Name</label>
                  <input
                    type="text"
                    value={formData.auth_env_var}
                    onChange={(e) => setFormData({ ...formData, auth_env_var: e.target.value })}
                    placeholder="e.g. INDIAMART_API_KEY (leave empty if public)"
                    className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-mono text-xs text-slate-900 focus:border-emerald-500 focus:outline-hidden"
                  />
                  <p className="mt-1 text-2xs text-slate-500">
                    Security Rule: Database stores <strong>only</strong> the environment variable name, never the raw key or token.
                  </p>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">Execution Frequency</label>
                <select
                  value={formData.schedule_interval_minutes}
                  onChange={(e) => setFormData({ ...formData, schedule_interval_minutes: Number(e.target.value) })}
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-slate-900 focus:border-emerald-500 focus:outline-hidden"
                >
                  {SCHEDULE_OPTIONS.map((opt) => (
                    <option key={opt.minutes} value={opt.minutes}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {formData.source_type === 'scrape' && (
                <div className="rounded-lg bg-amber-50 p-3 border border-amber-200 space-y-2">
                  <div className="text-xs font-semibold text-amber-900">Scraping Ethics & DPDP Act Compliance</div>
                  <p className="text-2xs text-amber-800">
                    The background scheduler automatically queries <code>robots.txt</code> before every single run using Python's <code>urllib.robotparser</code>. Runs with bot identifier User-Agent and polite rate limits.
                  </p>
                  <label className="flex items-center gap-2 text-xs font-medium text-amber-900 cursor-pointer pt-1">
                    <input
                      type="checkbox"
                      checked={formData.terms_checked}
                      onChange={(e) => setFormData({ ...formData, terms_checked: e.target.checked })}
                      className="rounded border-amber-400 text-amber-600 focus:ring-amber-500"
                    />
                    I have checked this website's terms of service and confirmed data collection is permitted.
                  </label>
                </div>
              )}

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="modal_is_active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <label htmlFor="modal_is_active" className="text-xs font-medium text-slate-700 cursor-pointer">
                  Source active and running on schedule
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-800 transition"
                >
                  {editingSource ? 'Save Changes' : 'Create Source'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
