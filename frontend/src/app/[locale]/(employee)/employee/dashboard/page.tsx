// Screen 05: Employee Dashboard
import AvailabilityToggle from '@/components/employee/AvailabilityToggle';
import AttendancePunchCard from '@/components/employee/AttendancePunchCard';

export default function EmployeeDashboard() {
  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Good afternoon, Priya</h1>
          <div className="flex gap-2 mt-1">
            <span className="bg-amber-100 text-amber-800 text-xs px-2 py-0.5 rounded font-medium">Coffee</span>
            <span className="bg-emerald-100 text-emerald-800 text-xs px-2 py-0.5 rounded font-medium">Tea</span>
          </div>
        </div>
        <AvailabilityToggle />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg border shadow-sm">
          <p className="text-xs text-slate-500 font-semibold uppercase">Total Tasks</p>
          <p className="text-2xl font-bold text-slate-800 mt-1">28</p>
        </div>
        <div className="bg-white p-4 rounded-lg border shadow-sm">
          <p className="text-xs text-slate-500 font-semibold uppercase">Completed</p>
          <p className="text-2xl font-bold text-emerald-600 mt-1">21</p>
        </div>
        <div className="bg-white p-4 rounded-lg border shadow-sm">
          <p className="text-xs text-slate-500 font-semibold uppercase">Pending</p>
          <p className="text-2xl font-bold text-amber-600 mt-1">7</p>
        </div>
        <div className="bg-white p-4 rounded-lg border shadow-sm">
          <p className="text-xs text-slate-500 font-semibold uppercase">Closed Won</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">16</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white p-5 rounded-lg border shadow-sm">
          <h2 className="font-semibold text-slate-800 mb-4">Active Tasks</h2>
          <p className="text-sm text-slate-500">Tasks assigned via auto-scheduler or Order Boards.</p>
        </div>
        <AttendancePunchCard />
      </div>
    </div>
  );
}
