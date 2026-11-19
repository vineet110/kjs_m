// Website dark mode: shared by the public layout (server) and the ☀/☾ button (browser).

/** Where the visitor's choice is remembered in their browser */
export const THEME_KEY = 'kjs-theme';

/** Script that runs before the page paints: dark if chosen before, or (when allowed) if the device is in dark mode. */
export function themeScript(followSystem: boolean): string {
  const system = followSystem ? "matchMedia('(prefers-color-scheme: dark)').matches" : 'false';
  return `(function(){try{var t=localStorage.getItem('${THEME_KEY}');var d=t?t==='dark':${system};document.documentElement.classList.toggle('dark',d)}catch(e){}})()`;
}
