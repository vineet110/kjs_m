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
/** logo: an uploaded picture (Admin > Website > Partner logos), or null for the name only */
export type StripPartner = { name: string; logo: string | null };
type Props = { certs: Cert[]; partners: StripPartner[]; pxPerSecond: number };

function Items({ certs, partners, hidden }: { certs: Cert[]; partners: StripPartner[]; hidden?: boolean }) {
  return (
    <>
      <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Certified</span>
      {certs.map((c) => (
        <Image key={c.name} src={c.img} alt={hidden ? '' : c.name} width={80} height={44} className="h-12 w-auto shrink-0 rounded-lg border border-slate-200 bg-white object-contain p-1 shadow-sm" />
      ))}
      <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Co-manufacturing partner to</span>
      {partners.map((p, i) => (
        <span key={`${p.name}-${i}`} className="flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full border border-gold/50 bg-gold/5 py-1 pl-1 pr-3 text-sm font-semibold text-slate-700">
          {p.logo ? (
            // White chip in both themes (bg-[#FFFFFF], not bg-white): coloured logos stay visible in dark mode
            <span className="flex h-9 w-12 items-center justify-center rounded-full bg-[#FFFFFF] p-1 ring-1 ring-slate-200">
              {/* eslint-disable-next-line @next/next/no-img-element -- an uploaded logo, already shrunk by the server */}
              <img src={p.logo} alt="" loading="lazy" className="max-h-full max-w-full object-contain" />
            </span>
          ) : (
            <span className="pl-2" />
          )}
          {p.name}
        </span>
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

  // Measured again whenever the strip or the list changes size: a resize, and each logo as it loads
  // (logos load late, and on an in-site page change the window "load" event has long passed)
  useEffect(() => {
    if (!moving || !box.current || !first.current) return;
    measure();
    let t: ReturnType<typeof setTimeout>;
    const ro = new ResizeObserver(() => { clearTimeout(t); t = setTimeout(measure, 100); });
    ro.observe(box.current);
    ro.observe(first.current);
    return () => { ro.disconnect(); clearTimeout(t); };
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
