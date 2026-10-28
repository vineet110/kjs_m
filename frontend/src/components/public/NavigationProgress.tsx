'use client';
// Runs the header's progress bar (ONE element, see ProgressBar) while another page of our site loads:
// after a click on a link, or when code navigates with startNavigationProgress() + router.push.
// It only sets <html data-navigating>; CSS shows the bar (globals.css). The same bar is also shown by
// CSS while a loading screen is on the page, so a click that ends in a loading screen keeps one
// smooth animation. Stops when the new page is shown, or after 10 s at most.
import { usePathname, useSearchParams } from 'next/navigation';
import { useEffect } from 'react';

let timer = 0;

/** Call before router.push(...) to another page: shows the bar until that page is shown. */
export function startNavigationProgress() {
  document.documentElement.setAttribute('data-navigating', '');
  window.clearTimeout(timer);
  timer = window.setTimeout(stopNavigationProgress, 10000);
}

function stopNavigationProgress() {
  document.documentElement.removeAttribute('data-navigating');
  window.clearTimeout(timer);
}

export default function NavigationProgress() {
  const pathname = usePathname();
  const search = useSearchParams();

  // New page shown: stop
  useEffect(stopNavigationProgress, [pathname, search]);

  useEffect(() => {
    // Capture phase on purpose. Next's <Link> always calls preventDefault() and then navigates itself
    // (node_modules/next/dist/client/app-dir/link.js, linkClicked), so in the bubble phase every
    // internal link click looks "cancelled" and the bar would never start. Next has no global
    // "navigation started" event; code that navigates itself calls startNavigationProgress().
    // A link that cancels its own navigation can opt out with data-no-progress; none do today.
    function onClick(e: MouseEvent) {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; // new tab / window
      const a = (e.target as Element | null)?.closest('a');
      if (!a || a.target === '_blank' || a.hasAttribute('download') || a.hasAttribute('data-no-progress')) return;
      const url = new URL(a.href, window.location.href);
      if (url.origin !== window.location.origin) return; // another website
      if (url.pathname === window.location.pathname && url.search === window.location.search) return; // same page or #anchor
      startNavigationProgress();
    }
    document.addEventListener('click', onClick, true);
    return () => {
      document.removeEventListener('click', onClick, true);
      stopNavigationProgress();
    };
  }, []);

  return null;
}
