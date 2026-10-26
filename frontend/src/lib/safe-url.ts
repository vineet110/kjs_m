// URL checks for values that come from outside our code (query strings, admin-edited links).

/** A link we are willing to render: one of our own pages ("/products") or an https:// site.
 *  Blocks javascript: links, which would run code as our website for whoever clicks them. */
export function safeLink(link: string | null | undefined): string | null {
  if (!link) return null;
  if (link.includes('\\')) return null; // browsers read "/\evil.com" as "//evil.com"
  if (link.startsWith('https://')) return link;
  if (link.startsWith('/') && !link.startsWith('//')) return link;
  return null;
}

/** Where to go after login (?next=...). Only a path on this same site, never another website
 *  (otherwise a phishing link could send staff to a fake "log in again" page). */
export function safeNext(next: string | null): string | null {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.includes('\\')) return null;
  try {
    const u = new URL(next, window.location.origin);
    return u.origin === window.location.origin ? u.pathname + u.search + u.hash : null;
  } catch {
    return null;
  }
}
