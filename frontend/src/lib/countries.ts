// Countries for the phone code and country pickers (UI step 7). The list itself is made by
// scripts/make_countries.py (countries-data.ts); flags are SVG files in public/flags (no package).
import { COUNTRY_ROWS } from './countries-data';

export type Country = { code: string; name: string; dial: string; main: boolean };

export const COUNTRIES: Country[] = COUNTRY_ROWS.map(([code, name, dial, main]) => ({ code, name, dial, main }));
const BY_CODE = new Map(COUNTRIES.map((c) => [c.code, c]));

/** Most enquiries and all staff are in India, so the pickers start there (until the visitor picks another). */
export const DEFAULT_COUNTRY = 'IN';
// No flag file for these two (not in flag-icons): the pickers show the letter code instead
export const NO_FLAG = new Set(['AC', 'TA']);

export const countryByCode = (code: string | null | undefined) => (code ? BY_CODE.get(code) : undefined);
export const countryByName = (name: string) => COUNTRIES.find((c) => c.name === name);

/** Lowercase without accents, so "cote" finds "Côte d’Ivoire". */
const plain = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

/**
 * Search as you type: digits (with or without +) match the phone code ("9" shows every +9…), letters match
 * the start of the name ("a" shows every country starting with A), then the start of a later word
 * ("emirates"). An empty search shows everything.
 */
export function filterCountries(query: string): Country[] {
  const q = plain(query.trim());
  if (!q) return COUNTRIES;
  const digits = q.replace(/^\+/, '');
  if (/^\d+$/.test(digits)) return COUNTRIES.filter((c) => c.dial.startsWith(digits));
  const first = COUNTRIES.filter((c) => plain(c.name).startsWith(q));
  if (q.length < 2) return first; // one letter: only names starting with it, as people expect
  const later = COUNTRIES.filter((c) => !first.includes(c) && plain(c.name).split(/[\s(),-]+/).some((w) => w.startsWith(q)));
  return [...first, ...later];
}

/** What is saved: "+91 98765 43210"; nothing when no number was typed (the form then refuses to send). */
export function composePhone(dial: string, number: string): string {
  const n = number.trim();
  return n ? `+${dial} ${n}` : '';
}

/**
 * A saved phone read back into the picker: the country (the one already picked if its code matches, else
 * the main country of that code, e.g. +1 = United States) and the rest of the number. A number saved
 * without a code (older data) keeps the default country.
 */
export function splitPhone(value: string, picked: string = DEFAULT_COUNTRY): { code: string; number: string } {
  const v = value.trim();
  const m = v.match(/^\+(\d+)(?:\s+(.*))?$/);
  if (m) {
    const pickedCountry = countryByCode(picked);
    const countryFor = (dial: string) =>
      pickedCountry?.dial === dial ? pickedCountry : COUNTRIES.find((c) => c.dial === dial && c.main);
    // "+971 50 …": the first group is the code
    const spaced = m[2] !== undefined ? countryFor(m[1]) : undefined;
    if (spaced) return { code: spaced.code, number: m[2] };
    // "+971501234567": the longest code that exists first (+971 before +97 before +9)
    for (let len = Math.min(4, m[1].length - 1); len >= 1; len--) {
      const c = countryFor(m[1].slice(0, len));
      if (c) return { code: c.code, number: (m[1].slice(len) + (m[2] ? ' ' + m[2] : '')).trim() };
    }
  }
  return { code: picked, number: v };
}

/**
 * A whole saved phone ("+91 98765 43210", or older text remembered by the browser) checked with exactly the
 * server's rule (schemas/common.py, Phone): optional +, digits, spaces, - ( ), 6 to 15 digits. Empty is fine.
 */
export function savedPhoneOk(value: string): boolean {
  const v = value.trim();
  if (!v) return true;
  const digits = v.replace(/[^0-9]/g, '').length;
  return /^\+?[0-9 ()-]+$/.test(v) && digits >= 6 && digits <= 15;
}

/**
 * Light check (decision 5a): only digits, spaces, - ( ), and 6 to 15 digits counting the country code,
 * the same rule as the server (schemas/common.py, Phone). Empty is fine.
 */
export function phoneLooksValid(number: string, dial: string): boolean {
  // The typed part has no + of its own; the rule itself lives once, in savedPhoneOk
  return !number.trim() || (!number.includes('+') && savedPhoneOk(composePhone(dial, number)));
}
