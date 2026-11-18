// Website insights: the website's visitor tracker (Reports > Website insights shows what it collects).
// No cookie and no name. A random visit id lives in sessionStorage (gone when the tab closes).
// Events wait in a small queue and go to the API every few seconds, and when the tab is hidden.
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
// Same as the server's limits (backend site_insights_service / endpoints): longer text is cut, not refused
const QUERY_MAX = 100;
// A request sent while the tab closes ("keepalive") may be at most 64 KB in browsers; stay well below it
const CLOSING_SEND_MAX_BYTES = 48_000;

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

/** The site a visitor came from, as its address only ("https://www.google.com"): never the page or what was
 *  searched there. Undefined for our own pages (moving around our site is not a source). */
export function outsideReferrer(referrer: string, ownHost: string): string | undefined {
  if (!referrer) return undefined;
  try {
    const u = new URL(referrer);
    return u.host === ownHost ? undefined : u.origin;
  } catch {
    return undefined;
  }
}

/** Is this search worth recording? Long enough, and not the same words as the last one recorded. */
export function searchToRecord(query: string, last: string, minChars: number): string | null {
  const q = query.trim().replace(/\s+/g, ' ').toLowerCase().slice(0, QUERY_MAX);
  return q.length >= minChars && q !== last ? q : null;
}

/** Split events into requests: at most `max` events each, and (when `maxBytes` is given) small enough to
 *  send while the tab closes. One event too big on its own is dropped, never the others. */
export function batches(events: InsightEvent[], max: number, maxBytes?: number): InsightEvent[][] {
  const out: InsightEvent[][] = [];
  let cur: InsightEvent[] = [];
  let size = 0;
  for (const e of events) {
    const n = JSON.stringify(e).length + 1;
    if (maxBytes && n > maxBytes - 200) continue; // too big alone (200: room for the visit id and brackets)
    if (cur.length >= max || (maxBytes && size + n > maxBytes - 200)) {
      out.push(cur);
      cur = [];
      size = 0;
    }
    cur.push(e);
    size += n;
  }
  if (cur.length) out.push(cur);
  return out;
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
  const timer = setInterval(() => flush(), c.send_every_seconds * 1000);
  const closing = () => flush(true);
  const onHide = () => document.visibilityState === 'hidden' && closing();
  document.addEventListener('visibilitychange', onHide);
  window.addEventListener('pagehide', closing);
  return () => {
    cancelSearch(); // a search waiting for its pause must not land in a tracker started later
    flush(true);
    clearInterval(timer);
    document.removeEventListener('visibilitychange', onHide);
    window.removeEventListener('pagehide', closing);
    config = null;
  };
}

export function track(e: InsightEvent) {
  if (!config) return;
  if (e.kind === 'click' && !config.buttons.includes(e.button)) return; // not counted (site_insights.ini)
  queue.push(e);
  if (queue.length >= config.max_events_per_send) flush();
}

/** Call on every change of the search box. Records it after the visitor stops typing for a moment, on the
 *  page where it was typed (even if they open a result before the pause ends). */
export function trackSearch(query: string, results: number) {
  if (!config) return;
  cancelSearch();
  const path = window.location.pathname;
  const min = config.min_search_chars;
  searchTimer = setTimeout(() => {
    searchTimer = undefined;
    const q = searchToRecord(query, lastSearch, min);
    if (!q) return;
    lastSearch = q;
    track({ kind: 'search', path, query: q, results });
  }, config.search_pause_ms);
}

/** Forget a search still waiting for its pause (the box was cleared, or the search box closed). */
export function cancelSearch() {
  clearTimeout(searchTimer);
  searchTimer = undefined;
}

/** Send what is waiting. `closing`: the tab is closing or hidden, so the request must be able to finish
 *  after the page is gone (keepalive, which has a size limit). Errors are ignored: insights must never get
 *  in a visitor's way. */
export function flush(closing = false) {
  if (!config || !queue.length) return;
  const events = queue;
  queue = [];
  for (const b of batches(events, config.max_events_per_send, closing ? CLOSING_SEND_MAX_BYTES : undefined)) {
    fetch('/api/v1/public/insights/events', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ visit_id: visitId, events: b }),
      credentials: 'same-origin',
      keepalive: closing,
    }).catch(() => {});
  }
}
