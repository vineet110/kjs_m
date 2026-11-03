'use client';
// Number tiles for the admin overview (UI updates part 2, step 2): a coloured icon circle, a number that
// counts up when the page opens, and an optional trend line ("▲ 3 vs last week").
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Icon, type IconName } from './icons';

/** Counts from 0 up to `target` in about `ms` (eases out, so it slows down at the end). Shows the final
 * number at once for people who ask their system for less motion. */
export function useCountUp(target: number, ms = 800) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || target === 0) {
      setN(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const step = (t: number) => {
      const p = Math.min(1, (t - start) / ms);
      setN(Math.round(target * (1 - (1 - p) ** 3)));
      if (p < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, ms]);
  return n;
}

// Each colour: the icon circle, plus the number colour when the tile needs attention
const TONES = {
  blue: 'bg-sky-100 text-sky-700',
  green: 'bg-emerald-100 text-emerald-700',
  gold: 'bg-gold/20 text-gold-dark',
  violet: 'bg-violet-100 text-violet-700',
  slate: 'bg-slate-100 text-slate-600',
} as const;

export type Tone = keyof typeof TONES;

/** "▲ 3 vs last week" (green), "▼ 2 vs last week" (red) or "Same as last week" (grey). */
function Trend({ now, before }: { now: number; before: number }) {
  const diff = now - before;
  if (diff === 0) return <p className="mt-1 text-xs text-slate-400">Same as last week</p>;
  const up = diff > 0;
  return (
    <p className={`mt-1 text-xs font-semibold ${up ? 'text-emerald-600' : 'text-red-600'}`}>
      <span aria-hidden>{up ? '▲' : '▼'}</span> {Math.abs(diff)} {up ? 'more' : 'fewer'} than last week
    </p>
  );
}

export default function StatTile({ label, value, icon, tone, href, alert, hint, trend }: {
  label: string; value: number; icon: IconName; tone: Tone; href?: string;
  alert?: boolean; // the number needs action (e.g. people waiting): shown in the tile's colour, with a dot
  hint?: string; // small grey line under the number
  trend?: { now: number; before: number };
}) {
  const shown = useCountUp(value);
  const body = (
    <div className={`card relative h-full p-4 transition duration-200 motion-reduce:transition-none ${href ? 'hover:-translate-y-0.5 hover:shadow-md' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${TONES[tone]}`}>
          <Icon name={icon} />
        </span>
      </div>
      {/* The real number for screen readers; the counting one is only for the eye */}
      <p className={`mt-1 text-3xl font-bold tabular-nums ${alert ? TONES[tone].split(' ')[1] : ''}`}>
        <span aria-hidden>{shown}</span>
        <span className="sr-only">{value}</span>
      </p>
      {trend ? <Trend {...trend} /> : hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
      {alert && <span aria-hidden className="absolute left-2 top-2 h-2 w-2 animate-pulse rounded-full bg-gold motion-reduce:animate-none" />}
    </div>
  );
  return href ? <Link href={href} className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold">{body}</Link> : body;
}
