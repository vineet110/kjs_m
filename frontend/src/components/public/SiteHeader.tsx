import Image from 'next/image';
import Link from 'next/link';
import { SITE } from '@/lib/site';

const NAV = [
  { href: '/', label: 'Home' },
  { href: '/products', label: 'Products' },
  { href: '/capabilities/stick-pack-factory', label: 'Capabilities' },
  { href: '/contact', label: 'Contact' },
];

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-ink/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        <Link href="/" className="flex items-center" aria-label="KJS India home">
          <Image src="/images/kjs/logo/Kjs.png" alt="KJS India" width={140} height={32} priority className="h-8 w-auto" />
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className="rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-white/10 hover:text-white">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <a href={SITE.whatsapp} target="_blank" rel="noopener" className="btn-gold hidden sm:inline-flex">
            Connect with Sales
          </a>
          <Link href="/employee/login" className="rounded-md px-3 py-2 text-xs text-slate-400 hover:text-white">
            Staff login
          </Link>
        </div>
      </div>
    </header>
  );
}
