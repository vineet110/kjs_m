'use client';
// The big banner in the middle of the home page. Slides change every few seconds (site_ui.ini
// slide_seconds) and pause on hover.
// With the striped line on, the line drives the slides: when it is full, the next slide shows, and it
// pauses with the hover, so line and slide never drift apart. "Reduce motion": no line, a plain timer.
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { isUploaded } from '@/lib/catalogue';

export type Slide = { eyebrow: string; title: string; text: string; href: string; cta: string; images: string[]; tone: string };

type Props = { slides: Slide[]; slideSeconds?: number; line?: boolean };

export default function HeroCarousel({ slides, slideSeconds = 6, line = false }: Props) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  useEffect(() => setReduced(window.matchMedia('(prefers-reduced-motion: reduce)').matches), []);
  const lineDrives = line && !reduced && slides.length > 1;
  const next = () => setI((n) => (n + 1) % slides.length);

  useEffect(() => {
    if (paused || slides.length < 2 || lineDrives) return;
    const t = setInterval(() => setI((n) => (n + 1) % slides.length), slideSeconds * 1000);
    return () => clearInterval(t);
  }, [paused, slides.length, lineDrives, slideSeconds]);

  return (
    <div
      className="relative h-full min-h-[360px] overflow-hidden rounded-xl ring-1 ring-gold/40 shadow-md"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      aria-roledescription="carousel"
    >
      {slides.map((s, n) => {
        return (
          <div
            key={n} // by position: two slides may share a title (the first one is editable in Admin)
            className={`absolute inset-0 flex bg-gradient-to-br transition-opacity duration-700 ${s.tone} ${n === i ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
            inert={n !== i} // hidden slides: no keyboard focus, hidden from screen readers
          >
            {/* Text slides in each time its slide becomes active (no motion for "reduce motion" users) */}
            <div
              className={`relative z-10 flex max-w-md flex-col justify-center p-6 md:p-10 ${
                n === i ? 'duration-700 animate-in fade-in slide-in-from-left-8 fill-mode-both motion-reduce:animate-none' : ''
              }`}
            >
              <p className="eyebrow">{s.eyebrow}</p>
              <h2 className="mt-3 text-2xl font-extrabold leading-tight text-ink md:text-[2.6rem] md:leading-[1.1]">
                {/* A hyphenated word ("Co-Manufacturing") never breaks at its hyphen */}
                {s.title.split(' ').map((w, k) => (
                  <span key={k}>{k > 0 && ' '}{w.includes('-') ? <span className="whitespace-nowrap">{w}</span> : w}</span>
                ))}
              </h2>
              <p className="mt-3 text-sm text-slate-700 md:text-base">{s.text}</p>
              <Link href={s.href} className="btn-dark mt-6 self-start">{s.cta} →</Link>
            </div>
            {/* Product packs fanned out on the right */}
            <div className="pointer-events-none absolute -right-6 bottom-0 top-0 hidden w-1/2 sm:block">
              {s.images.slice(0, 3).map((src, k) => (
                <Image
                  key={src}
                  src={src}
                  unoptimized={isUploaded(src)} // uploaded photos: the API may redirect to storage
                  alt=""
                  width={320}
                  height={240}
                  priority={n === 0}
                  // Packs pop in one after another when the slide shows
                  style={n === i ? { animationDelay: `${200 + k * 150}ms` } : undefined}
                  className={`absolute w-[58%] rounded-2xl shadow-xl ring-1 ring-black/5 ${
                    ['right-[30%] top-[10%] -rotate-6', 'right-[6%] top-[28%] rotate-3', 'right-[26%] top-[55%] -rotate-2'][k]
                  } ${n === i ? 'duration-700 animate-in fade-in zoom-in-90 slide-in-from-bottom-6 fill-mode-both motion-reduce:animate-none' : ''}`}
                />
              ))}
            </div>
          </div>
        );
      })}

      <div className="absolute bottom-4 left-6 z-20 flex gap-2 md:left-10">
        {slides.map((s, n) => (
          <button
            key={n}
            onClick={() => setI(n)}
            className={`h-2 rounded-full transition-all ${n === i ? 'w-8 bg-ink' : 'w-2 bg-ink/30 hover:bg-ink/50'}`}
            aria-label={`Show slide ${n + 1}`}
          />
        ))}
      </div>

      {/* Striped gold-and-charcoal line along the bottom, filling up while the slide shows */}
      {lineDrives && (
        <div className="absolute inset-x-0 bottom-0 z-20 h-[3px] bg-ink/10" aria-hidden="true">
          <div
            key={i} // a new slide restarts the line
            className="h-full w-0 animate-heroline bg-hazard"
            style={{ animationDuration: `${slideSeconds}s`, animationPlayState: paused ? 'paused' : 'running' }}
            onAnimationEnd={next}
          />
        </div>
      )}
    </div>
  );
}
