import Link from 'next/link';

export default function Header() {
  return (
    <header className="bg-white border-b sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="https://www.kjsindia.com/" target="_blank" className="font-extrabold text-xl tracking-tight text-blue-900">
          KJS <span className="text-amber-600">INDIA</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link href="/employee/login" className="text-sm font-semibold bg-slate-900 text-white px-3 py-1.5 rounded-md hover:bg-slate-800">
            Employee Login
          </Link>
        </div>
      </div>
    </header>
  );
}
