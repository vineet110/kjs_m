// Screen 14: Team Attendance Grid & Payroll Export
export default function TeamAttendancePage() {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-800">Team Attendance & Timesheets</h1>
        <button className="bg-emerald-700 text-white px-4 py-2 rounded-md font-medium text-sm hover:bg-emerald-800">
          Export to Excel
        </button>
      </div>
    </div>
  );
}
