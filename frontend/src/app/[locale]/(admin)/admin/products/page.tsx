'use client';
// Admin adds the real product list (backlog I2). No prices yet (I3).
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api, ApiFailure, type Category, type Product } from '@/lib/api';

export default function AdminProducts() {
  const [cats, setCats] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    api<Category[]>('/public/categories').then(setCats);
    api<Product[]>('/public/products').then(setProducts);
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form));
    try {
      await api('/admin/products', {
        method: 'POST',
        body: { ...f, private_label: f.private_label === 'on', is_best_seller: f.is_best_seller === 'on' },
      });
      setMsg({ ok: true, text: `Added "${f.name}". It is live on the website now.` });
      form.reset();
      load();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not save.' });
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Products</h1>
      <form onSubmit={add} className="card grid gap-3 p-5 md:grid-cols-2">
        <div><label className="label">Category</label>
          <select name="category_slug" className="input" required>{cats.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}</select>
        </div>
        <div><label className="label">Name</label><input name="name" required minLength={2} className="input" placeholder="Instant Coffee 3-in-1 Stick" /></div>
        <div><label className="label">Pack formats</label><input name="pack_formats" className="input" placeholder="Stick pack 18 g, Pouch 1 kg" /></div>
        <div><label className="label">Minimum order</label><input name="moq" className="input" placeholder="100,000 units" /></div>
        <div className="md:col-span-2"><label className="label">Description</label><textarea name="description" rows={3} className="input" /></div>
        <div><label className="label">Image path (in /public for now)</label><input name="image_path" className="input" placeholder="/images/products/coffee-stick.jpg" /></div>
        <div className="flex items-end gap-4 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" name="private_label" defaultChecked /> Private label</label>
          <label className="flex items-center gap-2"><input type="checkbox" name="is_best_seller" /> Best seller</label>
        </div>
        {msg && <p className={`rounded p-2 text-sm md:col-span-2 ${msg.ok ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-700'}`}>{msg.text}</p>}
        <div className="md:col-span-2"><button className="btn-dark">Add product</button></div>
      </form>

      <div className="card divide-y">
        {products.length === 0 && <p className="p-4 text-sm text-slate-500">No products yet.</p>}
        {products.map((p) => (
          <div key={p.id} className="flex items-center justify-between p-3 text-sm">
            <div><span className="font-medium">{p.name}</span> <span className="text-slate-500">· {p.category_name}{p.is_best_seller ? ' · best seller' : ''}</span></div>
            <Link href={`/products/${p.slug}`} target="_blank" className="text-xs underline">View</Link>
          </div>
        ))}
      </div>
    </div>
  );
}
