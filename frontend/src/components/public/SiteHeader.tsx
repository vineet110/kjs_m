import Image from 'next/image';
import Link from 'next/link';
import { Suspense } from 'react';
import NavigationProgress from './NavigationProgress';
import ProgressBar from './ProgressBar';
import { SITE } from '@/lib/site';
import { asset } from '@/lib/assets';

const NAV = [
  { href: '/', label: 'Home' },
  { href: '/products', label: 'Products' },
  { href: '/private-label', label: 'Private label', key: 'private' },
  { href: '/partners', label: 'Partners', key: 'partners' },
  { href: '/contact', label: 'Contact' },
];

export default function SiteHeader({ showPartners = true, showPrivateLabel = true }: { showPartners?: boolean; showPrivateLabel?: boolean }) {
  const nav = NAV.filter((n) => (n.key === 'partners' ? showPartners : n.key === 'private' ? showPrivateLabel : true));
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-ink/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        <Link href="/" className="flex items-center" aria-label="KJS India home">
          <Image src={asset('/images/kjs/logo/Kjs.png')} alt="KJS India" width={140} height={32} priority className="h-8 w-auto" />
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          {nav.map((n) => (
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
      {/* The page-loading bar on the header's bottom edge. Shown by CSS (globals.css, .page-progress)
          while a page loads (NavigationProgress) or a loading screen is on the page. Suspense:
          NavigationProgress reads the URL (useSearchParams); fallback null, so pages never stream. */}
      <ProgressBar className="page-progress" />
      <Suspense fallback={null}>
        <NavigationProgress />
      </Suspense>
    </header>
  );
}
