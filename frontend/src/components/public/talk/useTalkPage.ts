'use client';
// Where the site talks: the home page only, unless site_ui.ini talk_all_pages = true.
import { usePathname } from 'next/navigation';

export function useTalkPage(allPages: boolean): boolean {
  const path = usePathname() || '/';
  // "/" or a language home such as "/en"
  return allPages || path === '/' || /^\/[a-z]{2}\/?$/.test(path);
}

/** A popup window (enquiry form, connect popup, quick view) or the Koko chat is open: don't talk over it. */
export const somethingOpen = () =>
  typeof document !== 'undefined' && !!document.querySelector('[aria-modal="true"], [aria-label="Close chat"]');

/** Once per visit (sessionStorage); a private window may refuse it, then it simply repeats. */
export const once = {
  done(key: string): boolean {
    try { return sessionStorage.getItem(`kjs-talk-${key}`) === '1'; } catch { return false; }
  },
  mark(key: string) {
    try { sessionStorage.setItem(`kjs-talk-${key}`, '1'); } catch { /* private window */ }
  },
};
