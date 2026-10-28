'use client';
// A gold bar running under the header while the next page loads, after a click on a link to another
// page of our site. Gives feedback on every page without a loading.tsx (which would turn 404 pages
// into 200, see (home)/loading.tsx). It stops when the new page is shown, or after 15 s at most.
import { usePathname, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';

export default function NavigationProgress() {
  const pathname = usePathname();
  const search = useSearchParams();
  const [busy, setBusy] = useState(false);

  // New page shown: stop
  useEffect(() => setBusy(false), [pathname, search]);

  useEffect(() => {
    let timer = 0;
    function onClick(e: MouseEvent) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest('a');
      if (!a || a.target === '_blank' || a.hasAttribute('download')) return;
      const url = new URL(a.href, window.location.href);
      if (url.origin !== window.location.origin) return; // another website
      if (url.pathname === window.location.pathname && url.search === window.location.search) return; // same page or #anchor
      setBusy(true);
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setBusy(false), 15000);
    }
    // Capture phase: runs before Next's <Link>, which calls preventDefault() to do its own navigation
    document.addEventListener('click', onClick, true);
    return () => {
      document.removeEventListener('click', onClick, true);
      window.clearTimeout(timer);
    };
  }, []);

  if (!busy) return null;
  return (
    <div className="fixed inset-x-0 top-16 z-50 h-1 overflow-hidden bg-gold/15" role="progressbar" aria-label="Loading page">
      <div className="h-full w-1/4 animate-progress rounded-full bg-gradient-to-r from-gold-light via-gold to-gold-dark motion-reduce:w-full motion-reduce:animate-none" />
    </div>
  );
}
