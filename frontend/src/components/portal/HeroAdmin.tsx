'use client';
// Admin > Website > Hero: the home page banner's slides and the numbers in the stats box.
// No slide switched on: the home page shows its built-in slides. No number on: the live catalogue counts.
// Pictures go up through the normal files route (owner website/hero) and are shrunk by the server.
import { useCallback, useEffect, useState } from 'react';
import { Msg, Pill } from '@/components/portal/ui';
import { useToast } from '@/components/portal/Toast';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';
import { api, ApiFailure, upload, type AdminHero, type AdminHeroSlide, type AdminHeroStat, type HeroTone, type StoredFile } from '@/lib/api';

const TONE_LABEL: Record<HeroTone, string> = { gold: 'Gold', rose: 'Rose', cream: 'Light yellow' };
const TONE_SWATCH: Record<HeroTone, string> = { gold: 'bg-[#F8DDAE]', rose: 'bg-[#F4D3CD]', cream: 'bg-[#FBE7A8]' };
const fail = (e: unknown, fallback: string) => (e instanceof ApiFailure ? e.message : fallback);

type Draft = Omit<AdminHeroSlide, 'id' | 'images'> & { id?: number; images: string[] };
const EMPTY: Draft = { eyebrow: '', title: '', text: '', cta_text: '', cta_link: '', tone: 'gold', image_ids: [], images: [], is_active: true, sort_order: 0 };

export default function HeroAdmin() {
  const [data, setData] = useState<AdminHero | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const [editing, setEditing] = useState<Draft | null>(null);
  const load = useCallback(() => {
    setLoadErr(null);
    api<AdminHero>('/content/hero').then(setData).catch(setLoadErr);
  }, []);
  useEffect(load, [load]);

  if (loadErr) return <LoadError error={loadErr} onRetry={load} />;
  if (!data) return <Loading />;
  const activeSlides = data.slides.filter((s) => s.is_active).length;
  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="font-semibold">Banner slides</h2>
            <p className="text-xs text-slate-500">
              {activeSlides === 0 ? 'None switched on: the home page shows its built-in slides.' : `${activeSlides} of at most ${data.max_slides} switched on.`}
            </p>
          </div>
          {!editing && <button onClick={() => setEditing({ ...EMPTY, sort_order: data.slides.length })} className="btn-dark">New slide</button>}
        </div>
        {editing && <SlideForm draft={editing} hero={data} onDone={() => { setEditing(null); load(); }} onCancel={() => setEditing(null)} />}
        <div className="card divide-y">
          {data.slides.length === 0 && <p className="p-4 text-sm text-slate-500">No slides yet.</p>}
          {data.slides.map((s) => <SlideRow key={s.id} s={s} onEdit={() => setEditing({ ...s })} onChange={load} />)}
        </div>
      </section>
      <Stats hero={data} onChange={load} />
    </div>
  );
}

function SlideRow({ s, onEdit, onChange }: { s: AdminHeroSlide; onEdit: () => void; onChange: () => void }) {
  const toast = useToast();
  async function patch(body: Partial<AdminHeroSlide>) {
    try { await api(`/content/hero/slides/${s.id}`, { method: 'PATCH', body }); onChange(); }
    catch (e) { toast(fail(e, 'Could not change it. Please try again.'), 'error'); }
  }
  async function remove() {
    if (!confirm(`Delete the slide "${s.title}"?`)) return;
    try { await api(`/content/hero/slides/${s.id}`, { method: 'DELETE' }); onChange(); }
    catch (e) { toast(fail(e, 'Could not delete it. Please try again.'), 'error'); }
  }
  return (
    <div className="flex flex-wrap items-center gap-3 p-3 text-sm">
      <span className={`h-10 w-3 shrink-0 rounded ${TONE_SWATCH[s.tone]}`} aria-hidden="true" />
      <div className="flex gap-1">
        {/* eslint-disable-next-line @next/next/no-img-element -- small admin thumbnails */}
        {s.images.map((src) => <img key={src} src={src} alt="" className="h-10 w-10 rounded object-cover ring-1 ring-slate-200" />)}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{s.title}</p>
        <p className="truncate text-xs text-slate-500">{s.eyebrow || 'No label'} · order {s.sort_order}</p>
      </div>
      <Pill value={s.is_active ? 'ok' : 'off'} label={s.is_active ? 'on' : 'off'} />
      <span className="flex gap-3 text-xs">
        <button onClick={onEdit} className="underline">Edit</button>
        <button onClick={() => patch({ is_active: !s.is_active })} className="underline">{s.is_active ? 'Switch off' : 'Switch on'}</button>
        <button onClick={remove} className="text-red-700 underline">Delete</button>
      </span>
    </div>
  );
}

function SlideForm({ draft, hero, onDone, onCancel }: { draft: Draft; hero: AdminHero; onDone: () => void; onCancel: () => void }) {
  const [d, setD] = useState<Draft>(draft);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD((x) => ({ ...x, [k]: v }));

  async function addPicture(slot: number, file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setMsg(null);
    const form = new FormData();
    form.append('owner_type', 'website');
    form.append('owner_id', 'hero');
    form.append('is_public', 'true');
    form.append('file', file);
    try {
      const f = await upload<StoredFile>('/files', form);
      const ids = [...d.image_ids];
      const images = [...d.images];
      ids[slot] = f.id;
      images[slot] = `/api/v1/public/files/${f.id}`;
      setD((x) => ({ ...x, image_ids: ids.filter(Boolean), images: images.filter(Boolean) }));
    } catch (e) {
      setMsg({ ok: false, text: fail(e, 'Could not upload the picture.') });
    } finally {
      setBusy(false);
    }
  }
  function removePicture(slot: number) {
    setD((x) => ({ ...x, image_ids: x.image_ids.filter((_, i) => i !== slot), images: x.images.filter((_, i) => i !== slot) }));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    const body = { eyebrow: d.eyebrow, title: d.title, text: d.text, cta_text: d.cta_text, cta_link: d.cta_link, tone: d.tone, image_ids: d.image_ids, is_active: d.is_active, sort_order: d.sort_order };
    try {
      await api(d.id ? `/content/hero/slides/${d.id}` : '/content/hero/slides', { method: d.id ? 'PATCH' : 'POST', body });
      onDone();
    } catch (err) {
      setMsg({ ok: false, text: fail(err, 'Could not save.') });
      setBusy(false);
    }
  }

  const slots = Array.from({ length: hero.max_images }, (_, i) => i);
  return (
    <form onSubmit={save} className="card grid gap-3 p-4 md:grid-cols-6">
      <div className="md:col-span-2"><label className="label" htmlFor="h-eyebrow">Small label (optional)</label><input id="h-eyebrow" value={d.eyebrow} onChange={(e) => set('eyebrow', e.target.value)} maxLength={60} className="input" placeholder="Private label" /></div>
      <div className="md:col-span-4"><label className="label" htmlFor="h-title">Title</label><input id="h-title" value={d.title} onChange={(e) => set('title', e.target.value)} required minLength={3} maxLength={80} className="input" placeholder="Your brand on our proven recipes" /></div>
      <div className="md:col-span-6"><label className="label" htmlFor="h-text">Text (optional)</label><textarea id="h-text" value={d.text} onChange={(e) => set('text', e.target.value)} maxLength={240} rows={2} className="input" /></div>
      <div className="md:col-span-2"><label className="label" htmlFor="h-cta">Button text (optional)</label><input id="h-cta" value={d.cta_text} onChange={(e) => set('cta_text', e.target.value)} maxLength={30} className="input" placeholder="Explore the range" /></div>
      <div className="md:col-span-2"><label className="label" htmlFor="h-link">Button link (optional)</label><input id="h-link" value={d.cta_link} onChange={(e) => set('cta_link', e.target.value)} maxLength={255} className="input" placeholder="/private-label" /></div>
      <div><label className="label" htmlFor="h-order">Order</label><input id="h-order" type="number" value={d.sort_order} onChange={(e) => set('sort_order', Number(e.target.value || 0))} className="input" /></div>
      <div><label className="label" htmlFor="h-tone">Colour</label>
        <select id="h-tone" value={d.tone} onChange={(e) => set('tone', e.target.value as HeroTone)} className="input">
          {hero.tones.map((t) => <option key={t} value={t}>{TONE_LABEL[t] ?? t}</option>)}
        </select>
      </div>
      <div className="md:col-span-6">
        <p className="label">Pictures (up to {hero.max_images}; JPG, PNG or WebP; made smaller automatically)</p>
        <div className="flex flex-wrap gap-3">
          {slots.map((i) => (
            <div key={i} className="flex flex-col items-center gap-1">
              <label className="flex h-20 w-20 cursor-pointer items-center justify-center overflow-hidden rounded-lg border border-dashed border-slate-300 text-xs text-slate-500 hover:border-gold" htmlFor={`h-pic-${i}`}>
                {/* eslint-disable-next-line @next/next/no-img-element -- admin preview of an uploaded picture */}
                {d.images[i] ? <img src={d.images[i]} alt={`Picture ${i + 1}`} className="h-full w-full object-cover" /> : i <= d.images.length ? '+ Add' : ''}
              </label>
              <input id={`h-pic-${i}`} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" disabled={busy || i > d.images.length} onChange={(e) => { addPicture(i, e.target.files?.[0]); e.target.value = ''; }} />
              {d.images[i] && <button type="button" onClick={() => removePicture(i)} className="text-xs text-red-700 underline">Remove</button>}
            </div>
          ))}
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm md:col-span-3"><input type="checkbox" checked={d.is_active} onChange={(e) => set('is_active', e.target.checked)} /> Show on the website</label>
      <div className="flex justify-end gap-2 md:col-span-3">
        <button type="button" onClick={onCancel} className="btn-ghost">Cancel</button>
        <button disabled={busy} className="btn-dark">{d.id ? 'Save slide' : 'Add slide'}</button>
      </div>
      <div className="md:col-span-6"><Msg msg={msg} /></div>
    </form>
  );
}

function Stats({ hero, onChange }: { hero: AdminHero; onChange: () => void }) {
  const toast = useToast();
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const active = hero.stats.filter((s) => s.is_active).length;

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    try {
      await api('/content/hero/stats', { method: 'POST', body: { number: f.number, label: f.label, sort_order: Number(f.sort_order || 0) } });
      setMsg({ ok: true, text: 'Number added.' });
      form.reset();
      onChange();
    } catch (err) {
      setMsg({ ok: false, text: fail(err, 'Could not save.') });
    }
  }
  async function patch(s: AdminHeroStat, body: Partial<AdminHeroStat>) {
    try { await api(`/content/hero/stats/${s.id}`, { method: 'PATCH', body }); onChange(); }
    catch (e) { toast(fail(e, 'Could not change it. Please try again.'), 'error'); }
  }
  async function remove(s: AdminHeroStat) {
    if (!confirm(`Delete "${s.number} ${s.label}"?`)) return;
    try { await api(`/content/hero/stats/${s.id}`, { method: 'DELETE' }); onChange(); }
    catch (e) { toast(fail(e, 'Could not delete it. Please try again.'), 'error'); }
  }

  return (
    <section className="space-y-3">
      <div>
        <h2 className="font-semibold">Numbers next to the banner</h2>
        <p className="text-xs text-slate-500">
          {active === 0 ? 'None switched on: the home page shows the live counts from the catalogue.' : `${active} of at most ${hero.max_stats} switched on.`}
          {' '}Whole numbers count up on the page; text like “0.9–3 g” shows as written.
        </p>
      </div>
      <form onSubmit={add} className="card grid gap-3 p-4 md:grid-cols-6">
        <div><label className="label" htmlFor="s-number">Number</label><input id="s-number" name="number" required maxLength={12} className="input" placeholder="24" /></div>
        <div className="md:col-span-3"><label className="label" htmlFor="s-label">Label</label><input id="s-label" name="label" required minLength={2} maxLength={60} className="input" placeholder="items and pack sizes to choose from" /></div>
        <div><label className="label" htmlFor="s-order">Order</label><input id="s-order" type="number" name="sort_order" defaultValue={hero.stats.length} className="input" /></div>
        <div className="flex items-end"><button className="btn-dark w-full">Add</button></div>
        <div className="md:col-span-6"><Msg msg={msg} /></div>
      </form>
      <div className="card divide-y">
        {hero.stats.length === 0 && <p className="p-4 text-sm text-slate-500">No numbers yet.</p>}
        {hero.stats.map((s) => (
          <div key={s.id} className="flex flex-wrap items-center gap-2 p-3 text-sm">
            <span className="min-w-12 font-bold tabular-nums">{s.number}</span>
            <span className="flex-1">{s.label}</span>
            <span className="text-xs text-slate-500">order {s.sort_order}</span>
            <Pill value={s.is_active ? 'ok' : 'off'} label={s.is_active ? 'on' : 'off'} />
            <span className="flex gap-3 text-xs">
              <button onClick={() => patch(s, { is_active: !s.is_active })} className="underline">{s.is_active ? 'Switch off' : 'Switch on'}</button>
              <button onClick={() => remove(s)} className="text-red-700 underline">Delete</button>
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
