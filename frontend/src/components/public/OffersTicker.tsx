// Screen 01: CSS translation ticker with pause-on-hover
export default function OffersTicker() {
  const offers = [
    "Special contract packaging rates for festive tea cartons",
    "Instant Coffee spray-dried batches ready for Q4 dispatch",
    "Custom confectionery sachet filling up to 100,000 units/day"
  ];

  return (
    <div className="bg-amber-500 text-slate-900 text-sm font-medium py-2 overflow-hidden border-y border-amber-600">
      <div className="animate-ticker space-x-12">
        {offers.concat(offers).map((offer, idx) => (
          <span key={idx} className="inline-block px-4">
            ★ {offer}
          </span>
        ))}
      </div>
    </div>
  );
}
