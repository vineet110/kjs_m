// Screen 03: Category product catalog (After access gate form)
import CategoryGateModal from '@/components/public/CategoryGateModal';

export default function CategoryPage({ params }: { params: { slug: string } }) {
  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold capitalize text-slate-800">{params.slug} Products</h1>
      <p className="text-slate-500 mb-6">Browse our complete catalogue of contract manufacturing capabilities.</p>
      
      {/* Category Gate Modal triggers if visitor is not verified */}
      <CategoryGateModal categorySlug={params.slug} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-4 bg-white rounded-lg border shadow-sm">
          <h3 className="font-semibold text-lg">Instant Coffee Premix Sticks</h3>
          <p className="text-sm text-slate-500">Pouch & stick packing formats from 2g to 25g.</p>
        </div>
      </div>
    </div>
  );
}
