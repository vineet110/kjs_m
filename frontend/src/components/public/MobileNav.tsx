'use client';
// The header menu on phones (below md). The desktop links are hidden there, so without this a phone
// visitor had no way to reach Products, Private label, Partners or Contact from the header (TC-PUB-02).
// Closes when a link is followed (the header stays on screen between pages) and on Escape.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

type Item = { href: string; label: string };

export default function MobileNav({ items }: { items: Item[] }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const close = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [open]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="mobile-nav"
        aria-label={open ? 'Close menu' : 'Open menu'}
        className="flex h-11 w-11 items-center justify-center rounded-md text-slate-200 hover:bg-white/10"
      >
        <span aria-hidden className="text-xl leading-none">{open ? '✕' : '☰'}</span>
      </button>
      {open && (
        <nav id="mobile-nav" className="absolute inset-x-0 top-16 border-b border-white/10 bg-ink/95 px-4 py-2 shadow-lg backdrop-blur">
          {items.map((n) => (
            <Link key={n.href} href={n.href} className="block rounded-md px-3 py-3 text-base text-slate-200 hover:bg-white/10 hover:text-white">
              {n.label}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
