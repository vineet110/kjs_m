// Website insights: the website's visitor tracker (Reports > Website insights shows what it collects).
// Anonymous: no cookie, no name. A random visit id lives in sessionStorage (gone when the tab closes).
// Events wait in a small queue and go to the API every few seconds and when the tab is hidden.
// Settings come from config/site_insights.ini through /public/config (`insights`); nothing here is tunable.
//
// What is counted:
//   page   - every page opened (SiteTracker, on each address change)
//   search - what was typed in the search box, after a typing pause (trackSearch)
//   click  - buttons tagged data-track="<name>", phone links (call) and WhatsApp links (whatsapp)

export type InsightsConfig = {
  on: boolean; send_every_seconds: number; max_events_per_send: number;
  search_pause_ms: number; min_search_chars: number; buttons: string[];
};
export type InsightEvent =
  | { kind: 'page'; path: string; referrer?: string }
  | { kind: 'search'; path: string; query: string; results: number }
  | { kind: 'click'; path: string; button: string };

const VISIT_KEY = 'kjs_visit';

let config: InsightsConfig | null = null; // null = not started, or switched off
let queue: InsightEvent[] = [];
let visitId = '';
let searchTimer: ReturnType<typeof setTimeout> | undefined;
let lastSearch = '';

// ---------- Small rules (tested in tests/lib.test.mjs) ----------
/** The button a website enquiry form counts as, from its lead source (EnquiryButton). */
export function buttonForSource(source: string | undefined): string | null {
  const map: Record<string, string> = { price_sheet: 'price_sheet', spec_pdf: 'spec_sheet', sample: 'sample_quote', quote: 'sample_quote' };
  return (source && map[source]) || null;
}

/** A link that counts as a button without a tag: phone links are "call", WhatsApp links are "whatsapp". */
export function linkButton(href: string | null | undefined): string | null {
  if (!href) return null;
  if (href.startsWith('tel:')) return 'call';
  if (/^https:\/\/(wa\.me|api\.whatsapp\.com|web\.whatsapp\.com)\//.test(href)) return 'whatsapp';
  return null;
}

/** The site a visitor came from, or undefined for our own pages (moving around our site is not a source). */
export function outsideReferrer(referrer: string, ownHost: string): string | undefined {
  if (!referrer) return undefined;
  try {
    return new URL(referrer).host === ownHost ? undefined : referrer;
  } catch {
    return undefined;
  }
}

/** Is this search worth recording? Long enough, and not the same words as the last one recorded. */
export function searchToRecord(query: string, last: string, minChars: number): string | null {
  const q = query.trim().replace(/\s+/g, ' ').toLowerCase();
  return q.length >= minChars && q !== last ? q : null;
}

// ---------- The tracker ----------
function newVisitId(): string {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  try {
    const saved = sessionStorage.getItem(VISIT_KEY);
    if (saved && /^[A-Za-z0-9-]{8,40}$/.test(saved)) return saved;
    sessionStorage.setItem(VISIT_KEY, random);
  } catch {
    /* storage blocked (private window): one id for this page only */
  }
  return random;
}

/** Start (SiteTracker). Returns the function that stops it. Does nothing when switched off. */
export function startInsights(c: InsightsConfig | null): () => void {
  if (!c?.on || typeof window === 'undefined') return () => {};
  config = c;
  visitId = visitId || newVisitId();
  const timer = setInterval(flush, c.send_every_seconds * 1000);
  const onHide = () => document.visibilityState === 'hidden' && flush();
  document.addEventListener('visibilitychange', onHide);
  window.addEventListener('pagehide', flush);
  return () => {
    flush();
    clearInterval(timer);
    document.removeEventListener('visibilitychange', onHide);
    window.removeEventListener('pagehide', flush);
    config = null;
  };
}

export function track(e: InsightEvent) {
  if (!config) return;
  if (e.kind === 'click' && !config.buttons.includes(e.button)) return; // not counted (site_insights.ini)
  queue.push(e);
  if (queue.length >= config.max_events_per_send) flush();
}

/** Call on every change of the search box. Records it after the visitor stops typing for a moment. */
export function trackSearch(query: string, results: number) {
  if (!config) return;
  clearTimeout(searchTimer);
  const pause = config.search_pause_ms;
  const min = config.min_search_chars;
  searchTimer = setTimeout(() => {
    const q = searchToRecord(query, lastSearch, min);
    if (!q) return;
    lastSearch = q;
    track({ kind: 'search', path: window.location.pathname, query: q, results });
  }, pause);
}

/** Send what is waiting. `keepalive` lets the request finish even while the tab closes. Errors are ignored:
 *  insights must never get in a visitor's way. */
export function flush() {
  if (!config || !queue.length) return;
  while (queue.length) {
    const events = queue.splice(0, config.max_events_per_send);
    fetch('/api/v1/public/insights/events', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ visit_id: visitId, events }),
      credentials: 'same-origin',
      keepalive: true,
    }).catch(() => {});
  }
}
