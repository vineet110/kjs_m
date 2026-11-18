'use client';
// Website insights tracker (lib/insights.ts): counts page views and clicks on tracked buttons. Draws nothing.
// The page stays server-rendered: this only runs in the browser, after the page has loaded.
import { usePathname } from 'next/navigation';
import { useEffect, useRef } from 'react';
import { linkButton, outsideReferrer, startInsights, track, type InsightsConfig } from '@/lib/insights';

export default function SiteTracker({ config }: { config: InsightsConfig | null }) {
  const path = usePathname();
  const first = useRef(true);
  const on = !!config?.on;

  useEffect(() => {
    const stop = startInsights(config);
    if (!config?.on) return stop;
    // One listener for the whole page: data-track buttons, phone links and WhatsApp links
    const onClick = (e: MouseEvent) => {
      const el = (e.target as Element | null)?.closest?.('[data-track], a[href]');
      if (!el) return;
      const button = el.getAttribute('data-track') || linkButton(el.getAttribute('href'));
      if (button) track({ kind: 'click', path: window.location.pathname, button });
    };
    document.addEventListener('click', onClick, { capture: true });
    return () => {
      document.removeEventListener('click', onClick, { capture: true });
      stop();
    };
  }, [config]);

  useEffect(() => {
    if (!on) return; // also runs when tracking turns on later, for the page already open
    // Only the first recorded page of a visit says where the visitor came from
    const referrer = first.current ? outsideReferrer(document.referrer, window.location.host) : undefined;
    first.current = false;
    track({ kind: 'page', path, ...(referrer ? { referrer } : {}) });
  }, [path, on]);

  return null;
}
