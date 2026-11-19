'use client';
// "How it works" on the home page: the four steps light up 1 → 4, joined by a gold line, the first time
// they come into view (site_ui.ini steps_light_up). The text is in the server HTML from the start (Google
// and no-JS visitors see everything); only the gold colour arrives later. "Reduce motion": lit at once.
import { useEffect, useRef, useState } from 'react';

type Step = { title: string; text: string };
const STEP_MS = 450; // gap between two steps lighting up

export default function StepsLightUp({ steps }: { steps: Step[] }) {
  const ref = useRef<HTMLOListElement>(null);
  const [lit, setLit] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) {
      setLit(true);
      return;
    }
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setLit(true); io.disconnect(); }
    }, { threshold: 0.4 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <ol ref={ref} className="relative mt-8 grid gap-4 md:grid-cols-4">
      {/* The gold line joining the numbers (wide screens only), drawn left to right */}
      <span
        aria-hidden="true"
        className={`pointer-events-none absolute left-10 right-10 top-[38px] z-0 hidden h-0.5 origin-left bg-gold transition-transform ease-out motion-reduce:transition-none md:block ${lit ? 'scale-x-100' : 'scale-x-0'}`}
        style={{ transitionDuration: `${STEP_MS * steps.length}ms` }}
      />
      {steps.map((s, i) => (
        <li
          key={s.title}
          className={`relative z-10 rounded-xl border border-t-4 bg-ink-soft p-5 transition-colors duration-500 motion-reduce:transition-none ${lit ? 'border-white/10 border-t-gold' : 'border-white/10 border-t-white/20'}`}
          style={{ transitionDelay: lit ? `${i * STEP_MS}ms` : undefined }}
        >
          <span
            className={`flex h-9 w-9 items-center justify-center rounded-full text-sm font-extrabold ring-4 transition-colors duration-500 motion-reduce:transition-none ${lit ? 'bg-gold text-ink ring-gold/25' : 'bg-white/10 text-white/60 ring-white/5'}`}
            style={{ transitionDelay: lit ? `${i * STEP_MS}ms` : undefined }}
          >
            {i + 1}
          </span>
          <h3 className="mt-3 font-semibold">{s.title}</h3>
          <p className="mt-1 text-sm text-slate-300">{s.text}</p>
        </li>
      ))}
    </ol>
  );
}
