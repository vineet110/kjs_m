// Screen 12: Order Board Detail (5 Checkpoints: Procurement, Packaging, Production, Placement, Track)
export default function OrderBoardDetailPage({ params }: { params: { code: string } }) {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Board {params.code} - 5 Checkpoints</h1>
      <p className="text-sm text-slate-500">Time split calculation (% / days), step handoffs, and 50%/85%/100% deadline alerts.</p>
    </div>
  );
}
