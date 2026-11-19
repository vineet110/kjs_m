'use client';
// Home page trust strip, sliding (site_ui.ini partner_strip): certificates and the brands we make for,
// moving slowly to the left in a loop and pausing under the mouse.
//
// Never empty: one copy of the list is repeated until it is wider than the strip, then that whole copy is
// doubled. The track slides by exactly one copy, so the second copy is always coming in from the right
// while the first leaves on the left. Measured again on resize and when the logos finish loading.
// "Reduce motion" or no JavaScript: a still, wrapped row (the same content, nothing moves).
import Image from 'next/image';
import { useCallback, useEffect, useRef, useState } from 'react';

type Cert = { name: string; img: string };
type Props = { certs: Cert[]; partners: string[]; pxPerSecond: number };

function Items({ certs, partners, hidden }: { certs: Cert[]; partners: string[]; hidden?: boolean }) {
  return (
    <>
      <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Certified</span>
      {certs.map((c) => (
        <Image key={c.name} src={c.img} alt={hidden ? '' : c.name} width={80} height={44} className="h-12 w-auto shrink-0 rounded-lg border border-slate-200 bg-white object-contain p-1 shadow-sm" />
      ))}
      <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Co-manufacturing partner to</span>
      {partners.map((b) => (
        <span key={b} className="shrink-0 whitespace-nowrap rounded-full border border-gold/50 bg-gold/5 px-3 py-1 text-sm font-semibold text-slate-700">{b}</span>
      ))}
    </>
  );
}

export default function PartnerStrip({ certs, partners, pxPerSecond }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const first = useRef<HTMLDivElement>(null);
  const [moving, setMoving] = useState(false);
  const [repeats, setRepeats] = useState(1);
  const [seconds, setSeconds] = useState(40);

  const measure = useCallback(() => {
    const b = box.current, f = first.current;
    if (!b || !f) return;
    // Width of one list (the first copy holds `repeats` lists)
    const one = f.scrollWidth / Math.max(1, repeats);
    if (!one) return;
    const need = Math.max(1, Math.ceil((b.clientWidth + 100) / one));
    if (need !== repeats) { setRepeats(need); return; } // measured again after the redraw
    setSeconds(f.scrollWidth / pxPerSecond);
  }, [repeats, pxPerSecond]);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    setMoving(true);
  }, []);

  useEffect(() => {
    if (!moving) return;
    measure();
    let t: ReturnType<typeof setTimeout>;
    const onResize = () => { clearTimeout(t); t = setTimeout(measure, 200); };
    window.addEventListener('resize', onResize);
    window.addEventListener('load', measure);
    return () => { window.removeEventListener('resize', onResize); window.removeEventListener('load', measure); clearTimeout(t); };
  }, [moving, measure]);

  if (!moving) {
    // Server HTML, no JavaScript, "reduce motion": a still row that wraps on phones
    return (
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-x-6 gap-y-3 px-4 py-5">
        <Items certs={certs} partners={partners} />
      </div>
    );
  }

  const copy = (hidden: boolean) => Array.from({ length: repeats }, (_, n) => (
    <Items key={n} certs={certs} partners={partners} hidden={hidden || n > 0} />
  ));
  return (
    <div
      ref={box}
      className="group overflow-hidden py-5 [mask-image:linear-gradient(90deg,transparent,#000_6%,#000_94%,transparent)]"
    >
      <div className="flex w-max animate-marquee group-hover:[animation-play-state:paused]" style={{ animationDuration: `${seconds}s` }}>
        <div ref={first} className="flex shrink-0 items-center gap-6 pr-6">{copy(false)}</div>
        <div className="flex shrink-0 items-center gap-6 pr-6" aria-hidden="true">{copy(true)}</div>
      </div>
    </div>
  );
}
