'use client';
// A stat number on the home page that counts up from 0 the first time it is seen (about 1.3 s).
// Only plain whole numbers count ("24"); anything else ("0.9–3 g") shows as written. The server HTML has the
// real number (Google, no JavaScript, "reduce motion" all see it).
import { useEffect, useRef, useState } from 'react';

const DURATION_MS = 1300;

export default function CountUp({ value, className = '' }: { value: string; className?: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const target = /^\d{1,7}$/.test(value) ? Number(value) : null;
  const [shown, setShown] = useState(value);

  useEffect(() => {
    const el = ref.current;
    if (target === null || !el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let frame = 0;
    const run = () => {
      const t0 = performance.now();
      const step = (t: number) => {
        const k = Math.min(1, (t - t0) / DURATION_MS);
        setShown(String(Math.round(target * (1 - Math.pow(1 - k, 3))))); // eases out
        if (k < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    };
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { io.disconnect(); setShown('0'); run(); } });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(frame); };
  }, [target]);

  return <p ref={ref} className={`tabular-nums ${className}`}>{shown}</p>;
}
