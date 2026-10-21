'use client';
// Screen 06: Attendance Check-in / Check-out Punch
export default function AttendancePunchCard() {
  return (
    <div className="bg-white p-5 rounded-lg border shadow-sm space-y-4">
      <h3 className="font-semibold text-slate-800">Today's Attendance</h3>
      <p className="text-xs text-slate-500">Punches logged with verified server timestamps.</p>
      <button className="w-full bg-emerald-600 text-white font-medium py-2 rounded-md hover:bg-emerald-700 text-sm">
        Punch In
      </button>
    </div>
  );
}
