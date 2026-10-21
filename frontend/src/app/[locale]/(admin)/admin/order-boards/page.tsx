// Screen 11: Order Boards List & New Order Board Modal
export default function OrderBoardsAdminPage() {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-800">Order Boards</h1>
        <button className="bg-blue-700 text-white px-4 py-2 rounded-md font-medium text-sm hover:bg-blue-800">
          + New Order Board (ABC117-xxxx)
        </button>
      </div>
    </div>
  );
}
