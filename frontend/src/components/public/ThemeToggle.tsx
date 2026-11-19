'use client';
// ☀/☾ button in the website header: switches the website between light and dark (site_ui.ini
// theme_toggle). The choice is remembered in this browser. Colours: the dark map in globals.css
// (.site-shell), so the staff portal is never affected.
// The first paint is set by themeScript (in the public layout, before anything shows), so a dark-mode
// visitor never sees a white flash. This button only keeps that in step after it loads.
import { useEffect, useState } from 'react';
import { THEME_KEY as KEY } from '@/lib/theme';

function saved(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

export default function ThemeToggle({ followSystem }: { followSystem: boolean }) {
  const [dark, setDark] = useState(false);

  // After a page change inside the site the script above does not run again: apply the choice here too
  useEffect(() => {
    const t = saved();
    const d = t ? t === 'dark' : followSystem && window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.classList.toggle('dark', d);
    setDark(d);
  }, [followSystem]);

  const flip = () => {
    const d = !dark;
    document.documentElement.classList.toggle('dark', d);
    try { localStorage.setItem(KEY, d ? 'dark' : 'light'); } catch { /* private window: works until reload */ }
    setDark(d);
  };

  return (
    <button
      type="button"
      onClick={flip}
      // One label for both states: right from the first paint, before this script knows the theme
      aria-label="Switch between light and dark theme"
      aria-pressed={dark}
      title="Light or dark theme"
      className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 text-slate-300 transition hover:border-gold hover:text-gold motion-safe:hover:-rotate-12"
    >
      {/* The icon follows the page's own "dark" class (set before paint), so it is never the wrong one */}
      <svg className="hidden dark:block" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
      <svg className="dark:hidden" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
    </button>
  );
}
