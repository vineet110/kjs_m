export default function BestSellersSection() {
  return (
    <section className="space-y-4">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Best Sellers</h2>
          <p className="text-sm text-slate-500">Most requested manufacturing & packaging formats</p>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {["Premium Instant Coffee (Jar)", "Orthodox CTC Blend", "Hard Boiled Candies", "Premix Sachet (20g)"].map((item, i) => (
          <div key={i} className="bg-white p-4 rounded-lg border shadow-sm">
            <div className="h-32 bg-slate-100 rounded mb-3 flex items-center justify-center text-slate-400 text-xs">
              Product Image
            </div>
            <h4 className="font-semibold text-slate-900 text-sm">{item}</h4>
            <span className="text-xs text-blue-600 font-medium">Customizable Packing</span>
          </div>
        ))}
      </div>
    </section>
  );
}
