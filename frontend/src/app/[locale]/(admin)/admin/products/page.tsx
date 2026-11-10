'use client';
// Products: add, edit, hide/show, and upload photos / spec sheets (tick "Show on website").
// No prices yet (backlog I3).
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import FileList from '@/components/portal/FileList';
import { useToast } from '@/components/portal/Toast';
import { Msg, PageTitle, Pill } from '@/components/portal/ui';
import { api, ApiFailure, type Category, type Product } from '@/lib/api';
import LoadError from '@/components/ui/LoadError';

type Row = Product & { is_active: boolean };

/** Is a form value the same as the saved one? Empty and null count as the same, and so do the two kinds of
 *  line break a text box may give. */
function same(a: unknown, b: unknown) {
  const norm = (v: unknown) => (typeof v === 'string' ? v.replace(/\r\n/g, '\n') : v ?? '');
  return norm(a) === norm(b);
}

export default function AdminProducts() {
  const [cats, setCats] = useState<Category[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [editing, setEditing] = useState<Row | null>(null);
  const [filesFor, setFilesFor] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const toast = useToast();

  const load = useCallback(() => {
    setLoadErr(null);
    api<Category[]>('/public/categories').then(setCats).catch(setLoadErr);
    api<Row[]>('/admin/products').then(setProducts).catch(setLoadErr);
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form));
    const body: Record<string, unknown> = {
      ...f, private_label: f.private_label === 'on', is_best_seller: f.is_best_seller === 'on',
      offer_percent: f.offer_percent ? Number(f.offer_percent) : null, // empty = no offer
    };
    try {
      if (editing) {
        // Only the fields changed in this form are sent (the PATCH changes only what it gets). So saving
        // can't undo what another admin changed in the meantime in a field we didn't touch, and
        // hidden / shown is never sent: an edit never shows a product someone hid.
        const before = editing as unknown as Record<string, unknown>;
        const changed = Object.fromEntries(Object.entries(body).filter(([k, v]) => !same(v, before[k])));
        if (Object.keys(changed).length === 0) {
          setMsg(null);
          setEditing(null);
          toast('Nothing changed');
          return;
        }
        await api(`/admin/products/${editing.id}`, { method: 'PATCH', body: changed });
        setMsg(null);
        toast(`Saved "${f.name}". The website shows it within a minute`);
        setEditing(null);
      } else {
        await api('/admin/products', { method: 'POST', body });
        setMsg(null);
        toast(`Added "${f.name}". It is live on the website within a minute`);
      }
      form.reset();
      load();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save.' });
    }
  }

  async function toggleHidden(p: Row) {
    // Only hidden / shown is sent (an edit changes only what it sends), so this can't undo a change made
    // since the list loaded, in another tab or by someone else
    try {
      await api(`/admin/products/${p.id}`, { method: 'PATCH', body: { is_active: !p.is_active } });
      load();
    } catch (err) {
      toast(err instanceof ApiFailure ? err.message : 'Could not change it. Please try again.', 'error');
    }
  }

  // Without the categories the form can't be filled in (and an edit would send an empty category)
  if (loadErr) return <LoadError error={loadErr} onRetry={load} />;
  const e = editing;
  return (
    <div className="space-y-6">
      <PageTitle title="All Products" sub="Changes show on the website within a minute." />
      <form key={e?.id ?? 'new'} onSubmit={save} className="card grid gap-3 p-5 md:grid-cols-2">
        <h2 className="font-semibold md:col-span-2">{e ? `Edit: ${e.name}` : 'Add a product'}</h2>
        <div><label className="label">Category</label>
          <select name="category_slug" defaultValue={e?.category_slug} className="input" required>{cats.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}</select>
        </div>
        <div><label className="label">Name</label><input name="name" defaultValue={e?.name} required minLength={2} className="input" placeholder="Instant Coffee 3-in-1 Stick" /></div>
        <div><label className="label">Pack formats</label><input name="pack_formats" defaultValue={e?.pack_formats} className="input" placeholder="Stick pack 18 g, Pouch 1 kg" /></div>
        <div><label className="label">Minimum order</label><input name="moq" defaultValue={e?.moq} className="input" placeholder="100,000 units" /></div>
        <div className="md:col-span-2"><label className="label">Description</label><textarea name="description" defaultValue={e?.description} rows={3} className="input" /></div>
        <div><label className="label">Image path (optional; or upload a photo below)</label><input name="image_path" defaultValue={e?.image_path} className="input" placeholder="/images/products/coffee-stick.jpg" /></div>
        <div>
          <label className="label" htmlFor="offer_percent">Offer % (optional): shows &quot;Up to X% OFF&quot;</label>
          <input id="offer_percent" name="offer_percent" type="number" min={1} max={90} step={1} defaultValue={e?.offer_percent ?? ''} className="input" placeholder="Leave empty for no offer" />
        </div>
        <div className="flex items-end gap-4 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" name="private_label" defaultChecked={e ? e.private_label : true} /> Private label</label>
          <label className="flex items-center gap-2"><input type="checkbox" name="is_best_seller" defaultChecked={e?.is_best_seller} /> Best seller</label>
        </div>
        <div className="md:col-span-2"><Msg msg={msg} /></div>
        <div className="flex gap-2 md:col-span-2">
          <button className="btn-dark">{e ? 'Save changes' : 'Add product'}</button>
          {e && <button type="button" onClick={() => setEditing(null)} className="btn-ghost">Cancel</button>}
        </div>
      </form>

      <div className="card divide-y">
        {products.length === 0 && <p className="p-4 text-sm text-slate-500">No products yet.</p>}
        {products.map((p) => (
          <div key={p.id} className="space-y-2 p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{p.name}</span>
              <span className="text-slate-500">· {p.category_name}{p.is_best_seller ? ' · best seller' : ''}{p.offer_percent ? ` · up to ${p.offer_percent}% off` : ''}</span>
              {!p.is_active && <Pill value="off" label="hidden" />}
              <span className="ml-auto flex gap-3 text-xs">
                <button onClick={() => { setEditing(p); window.scrollTo({ top: 0, behavior: 'smooth' }); }} className="underline">Edit</button>
                <button onClick={() => setFilesFor(filesFor === p.slug ? null : p.slug)} className="underline">Photos & files</button>
                <button onClick={() => toggleHidden(p)} className="underline">{p.is_active ? 'Hide' : 'Show'}</button>
                {p.is_active && <Link href={`/products/${p.slug}`} target="_blank" className="underline">View</Link>}
              </span>
            </div>
            {filesFor === p.slug && <FileList ownerType="product" ownerId={p.slug} publicToggle />}
          </div>
        ))}
      </div>
    </div>
  );
}
