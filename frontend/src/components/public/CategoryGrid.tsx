import Link from 'next/link';

const categories = [
  { name: 'Coffee', slug: 'coffee', count: '14 Products' },
  { name: 'Tea', slug: 'tea', count: '18 Products' },
  { name: 'Confectionery', slug: 'confectionery', count: '22 Products' },
];

export default function CategoryGrid() {
  return (
    <section className="space-y-4">
      <h2 className="text-2xl font-bold text-slate-800">Product Categories</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {categories.map((c) => (
          <Link
            key={c.slug}
            href={`/categories/${c.slug}`}
            className="p-6 bg-white border rounded-xl hover:shadow-md transition-shadow"
          >
            <h3 className="text-xl font-bold text-slate-900">{c.name}</h3>
            <p className="text-sm text-slate-500 mt-1">{c.count}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
