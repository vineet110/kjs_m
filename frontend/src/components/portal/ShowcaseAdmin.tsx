'use client';
// Admin > Website: Partner logos (the home page's sliding strip) and Pop-up activity (true, recent activity the
// website shows as pop-ups, "A brand in Dubai requested a sample · 2 hours ago").
import { useCallback, useEffect, useState } from 'react';
import { Msg, Pill } from '@/components/portal/ui';
import { useToast } from '@/components/portal/Toast';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';
import { api, ApiFailure, upload, type AdminActivityLine, type AdminBrandPartner, type StoredFile } from '@/lib/api';

const fail = (e: unknown, fallback: string) => (e instanceof ApiFailure ? e.message : fallback);
type Note = { ok: boolean; text: string } | null;

/** Loads one admin list; `reload` after every change. */
function useAdminList<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const reload = useCallback(() => {
    setErr(null);
    api<T>(path).then(setData).catch(setErr);
  }, [path]);
  useEffect(reload, [reload]);
  return { data, err, reload };
}

async function uploadLogo(file: File): Promise<StoredFile> {
  const form = new FormData();
  form.append('owner_type', 'website');
  form.append('owner_id', 'partners');
  form.append('is_public', 'true');
  form.append('file', file);
  return upload<StoredFile>('/files', form);
}

// ---------- Partner logos ----------
export function PartnerLogosAdmin() {
  const { data, err, reload } = useAdminList<{ partners: AdminBrandPartner[]; max_partners: number }>('/content/showcase/partners');
  const toast = useToast();
  const [msg, setMsg] = useState<Note>(null);
  const [busy, setBusy] = useState(false);
  const [logo, setLogo] = useState<StoredFile | null>(null);

  if (err) return <LoadError error={err} onRetry={reload} />;
  if (!data) return <Loading />;
  const on = data.partners.filter((p) => p.is_active).length;

  async function pickLogo(file: File | undefined, then?: (id: number) => Promise<void>) {
    if (!file) return;
    setBusy(true);
    setMsg(null);
    try {
      const f = await uploadLogo(file);
      if (then) await then(f.id);
      else setLogo(f);
    } catch (e) {
      setMsg({ ok: false, text: fail(e, 'Could not upload the logo.') });
    } finally {
      setBusy(false);
    }
  }
  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    try {
      await api('/content/showcase/partners', { method: 'POST', body: { name: f.name, logo_file_id: logo?.id ?? null, sort_order: Number(f.sort_order || 0) } });
      setMsg({ ok: true, text: 'Partner added.' });
      form.reset();
      setLogo(null);
      reload();
    } catch (e2) {
      setMsg({ ok: false, text: fail(e2, 'Could not save.') });
    }
  }
  async function patch(p: AdminBrandPartner, body: Partial<AdminBrandPartner>) {
    try { await api(`/content/showcase/partners/${p.id}`, { method: 'PATCH', body }); reload(); }
    catch (e) { toast(fail(e, 'Could not change it. Please try again.'), 'error'); }
  }
  async function remove(p: AdminBrandPartner) {
    if (!confirm(`Delete the partner "${p.name}"?`)) return;
    try { await api(`/content/showcase/partners/${p.id}`, { method: 'DELETE' }); reload(); }
    catch (e) { toast(fail(e, 'Could not delete it. Please try again.'), 'error'); }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        {on === 0 ? 'None switched on: the sliding strip on the home page shows the built-in names.' : `${on} of at most ${data.max_partners} switched on.`}
        {' '}Logos: PNG with a transparent background looks best. They are made smaller automatically.
      </p>
      <form onSubmit={add} className="card grid gap-3 p-4 md:grid-cols-6">
        <div className="md:col-span-2"><label className="label" htmlFor="p-name">Name</label><input id="p-name" name="name" required minLength={2} maxLength={60} className="input" placeholder="Nestlé" /></div>
        <div className="md:col-span-2">
          <label className="label" htmlFor="p-logo">Logo (optional)</label>
          <input id="p-logo" type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={(e) => pickLogo(e.target.files?.[0])} className="block w-full text-xs" />
          {logo && <p className="mt-1 text-xs text-slate-500">Uploaded: {logo.name}</p>}
        </div>
        <div><label className="label" htmlFor="p-order">Order</label><input id="p-order" type="number" name="sort_order" defaultValue={data.partners.length} className="input" /></div>
        <div className="flex items-end"><button disabled={busy} className="btn-dark w-full">Add</button></div>
        <div className="md:col-span-6"><Msg msg={msg} /></div>
      </form>
      <div className="card divide-y">
        {data.partners.length === 0 && <p className="p-4 text-sm text-slate-500">No partners yet.</p>}
        {data.partners.map((p) => (
          <div key={p.id} className="flex flex-wrap items-center gap-3 p-3 text-sm">
            <span className="flex h-10 w-14 items-center justify-center rounded bg-[#FFFFFF] p-1 ring-1 ring-slate-200">
              {/* eslint-disable-next-line @next/next/no-img-element -- admin preview of an uploaded logo */}
              {p.logo ? <img src={p.logo} alt="" className="max-h-full max-w-full object-contain" /> : <span className="text-[10px] text-slate-400">no logo</span>}
            </span>
            <span className="flex-1 font-medium">{p.name}</span>
            <span className="text-xs text-slate-500">order {p.sort_order}</span>
            <Pill value={p.is_active ? 'ok' : 'off'} label={p.is_active ? 'on' : 'off'} />
            <span className="flex flex-wrap gap-3 text-xs">
              <label className="cursor-pointer underline">
                {p.logo ? 'Change logo' : 'Add logo'}
                <input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" disabled={busy}
                  onChange={(e) => { pickLogo(e.target.files?.[0], (id) => patch(p, { logo_file_id: id })); e.target.value = ''; }} />
              </label>
              {p.logo && <button onClick={() => patch(p, { logo_file_id: null })} className="underline">Remove logo</button>}
              <button onClick={() => patch(p, { is_active: !p.is_active })} className="underline">{p.is_active ? 'Switch off' : 'Switch on'}</button>
              <button onClick={() => remove(p)} className="text-red-700 underline">Delete</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- Pop-up activity ----------
/** "2026-11-19T15:30" in India time, for a datetime-local box */
const nowIST = () => new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Kolkata' }).slice(0, 16).replace(' ', 'T');
const fromIST = (v: string) => new Date(`${v}:00+05:30`).toISOString();
const showIST = (iso: string) => new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' });

export function ActivityAdmin() {
  const { data, err, reload } = useAdminList<{ lines: AdminActivityLine[]; max_age_days: number; max_shown: number }>('/content/showcase/activity');
  const toast = useToast();
  const [msg, setMsg] = useState<Note>(null);

  if (err) return <LoadError error={err} onRetry={reload} />;
  if (!data) return <Loading />;
  const oldBefore = Date.now() - data.max_age_days * 86_400_000;

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    try {
      await api('/content/showcase/activity', { method: 'POST', body: { text: f.text, happened_at: fromIST(f.happened_at), sort_order: Number(f.sort_order || 0) } });
      setMsg({ ok: true, text: 'Line added.' });
      form.reset();
      reload();
    } catch (e2) {
      setMsg({ ok: false, text: fail(e2, 'Could not save.') });
    }
  }
  async function patch(a: AdminActivityLine, body: Partial<AdminActivityLine>) {
    try { await api(`/content/showcase/activity/${a.id}`, { method: 'PATCH', body }); reload(); }
    catch (e) { toast(fail(e, 'Could not change it. Please try again.'), 'error'); }
  }
  async function remove(a: AdminActivityLine) {
    if (!confirm(`Delete "${a.text}"?`)) return;
    try { await api(`/content/showcase/activity/${a.id}`, { method: 'DELETE' }); reload(); }
    catch (e) { toast(fail(e, 'Could not delete it. Please try again.'), 'error'); }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        Real, recent activity only: the website shows each line as a pop-up with “2 hours ago”, “yesterday” and so on,
        worked out from the time you enter. Lines older than {data.max_age_days} days stop showing by themselves.
        No names or company details of buyers.
      </p>
      <form onSubmit={add} className="card grid gap-3 p-4 md:grid-cols-6">
        <div className="md:col-span-3"><label className="label" htmlFor="a-text">What happened</label><input id="a-text" name="text" required minLength={5} maxLength={120} className="input" placeholder="A brand in Dubai requested a sample" /></div>
        <div className="md:col-span-2"><label className="label" htmlFor="a-when">When (India time)</label><input id="a-when" type="datetime-local" name="happened_at" required max={nowIST()} defaultValue={nowIST()} className="input" /></div>
        <div className="flex items-end"><button className="btn-dark w-full">Add</button></div>
        <div className="md:col-span-6"><Msg msg={msg} /></div>
      </form>
      <div className="card divide-y">
        {data.lines.length === 0 && <p className="p-4 text-sm text-slate-500">No lines yet: no pop-ups show on the website.</p>}
        {data.lines.map((a) => {
          const old = new Date(a.happened_at).getTime() < oldBefore;
          return (
            <div key={a.id} className="flex flex-wrap items-center gap-2 p-3 text-sm">
              <span className="flex-1 font-medium">{a.text}</span>
              <span className="text-xs text-slate-500">{showIST(a.happened_at)}</span>
              {old && <Pill value="off" label="too old" />}
              <Pill value={a.is_active ? 'ok' : 'off'} label={a.is_active ? 'on' : 'off'} />
              <span className="flex gap-3 text-xs">
                <button onClick={() => patch(a, { is_active: !a.is_active })} className="underline">{a.is_active ? 'Switch off' : 'Switch on'}</button>
                <button onClick={() => remove(a)} className="text-red-700 underline">Delete</button>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
