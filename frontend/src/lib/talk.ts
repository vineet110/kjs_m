// The site talks (home page refresh, PR C): small helpers for the bubble, the pop-ups and the offer form.
// Pure functions, so they are tested in tests/lib.test.mjs.

/** "just now", "12 min ago", "2 hours ago", "yesterday", "3 days ago", "last week", "3 weeks ago", "this year". */
export function relTime(iso: string, now: number = Date.now()): string {
  const min = Math.round((now - new Date(iso).getTime()) / 60_000);
  if (!Number.isFinite(min)) return '';
  if (min < 2) return 'just now';
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  if (h < 24) return h === 1 ? '1 hour ago' : `${h} hours ago`;
  const d = Math.round(h / 24);
  if (d === 1) return 'yesterday';
  if (d < 7) return `${d} days ago`;
  const w = Math.round(d / 7);
  if (w === 1) return 'last week';
  return w < 5 ? `${w} weeks ago` : 'this year';
}

/** When pop-up number n (0, 1, 2 ...) shows, in seconds after the page opened. `times` rise (site_ui.ini
 *  popup_times, e.g. 5, 8, 11, 15, 17, 25); after the last one the same pattern repeats from there:
 *  5, 8, 11, 15, 17, 25, 30, 33, 36 ... */
export function popupAt(times: number[], n: number): number {
  if (!times.length) return Infinity;
  const cycle = times[times.length - 1];
  return Math.floor(n / times.length) * cycle + times[n % times.length];
}

/** A phone number the server will take: 10 to 15 digits (spaces, +, - and brackets allowed around them). */
export function phoneOk(v: string): boolean {
  const digits = v.replace(/\D/g, '');
  return /^\+?[0-9 ()-]+$/.test(v.trim()) && digits.length >= 10 && digits.length <= 15;
}
