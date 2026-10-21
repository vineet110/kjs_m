// Screen 08: Order board step view (Employee View)
export default function EmployeeOrderBoardStepPage({ params }: { params: { code: string } }) {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Order Board {params.code}</h1>
        <span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-xs font-semibold">Your Step: Packaging</span>
      </div>
      <p className="text-sm text-slate-500">Upload documents, review requirements, and monitor step countdown.</p>
    </div>
  );
}
