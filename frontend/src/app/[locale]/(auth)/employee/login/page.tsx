// Screen 04: Employee login
export default function EmployeeLoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 p-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-lg border p-8 space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-slate-900">KJS INDIA</h2>
          <p className="text-sm text-slate-500">Employee & Admin Portal</p>
        </div>
        <form className="space-y-4">
          <div>
            <label className="text-sm font-medium text-slate-700">Employee ID or Email</label>
            <input type="text" placeholder="KJS-EMP-014 or name@kjsindia.com" className="w-full mt-1 px-3 py-2 border rounded-md" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Password</label>
            <input type="password" placeholder="••••••••" className="w-full mt-1 px-3 py-2 border rounded-md" />
          </div>
          <button type="submit" className="w-full bg-blue-700 text-white py-2 rounded-md font-medium hover:bg-blue-800">
            Sign In
          </button>
        </form>
      </div>
    </div>
  );
}
