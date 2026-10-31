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
 *  (otherwise a phishing link could send staff to a fake "log in again" page), and never the login page
 *  itself (logging in would just show the form again, as if it had failed): null = go to the dashboard. */
export function safeNext(next: string | null): string | null {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.includes('\\')) return null;
  try {
    const u = new URL(next, window.location.origin);
    if (u.origin !== window.location.origin) return null;
    // Checked AFTER the URL is cleaned up: "/..//evil.com" (or "/.//", "/%2e%2e//") becomes "//evil.com",
    // which a browser reads as ANOTHER website
    if (u.pathname.startsWith('//')) return null;
    // The login page, however it is written: "/employee//login" (repeated slashes) or "/employee/%6Cogin"
    // (letters percent-encoded) are caught too
    let path = u.pathname;
    try {
      path = decodeURIComponent(path);
    } catch {
      return null; // broken encoding: not a link we made
    }
    if (/^\/([a-z]{2}\/)?employee\/login\/?$/i.test(path.replace(/\/{2,}/g, '/'))) return null;
    return u.pathname + u.search + u.hash;
  } catch {
    return null;
  }
}
