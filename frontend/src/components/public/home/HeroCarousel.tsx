'use client';
// The big banner in the middle of the home page. Slides change every 6 seconds and pause on hover.
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';

export type Slide = { eyebrow: string; title: string; text: string; href: string; cta: string; images: string[]; tone: string };

export default function HeroCarousel({ slides }: { slides: Slide[] }) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused || slides.length < 2) return;
    const t = setInterval(() => setI((n) => (n + 1) % slides.length), 6000);
    return () => clearInterval(t);
  }, [paused, slides.length]);

  return (
    <div
      className="relative h-full min-h-[340px] overflow-hidden rounded-xl ring-1 ring-gold/40 shadow-md"
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
              <h2 className="mt-3 text-2xl font-extrabold leading-tight text-ink md:text-4xl">{s.title}</h2>
              <p className="mt-3 text-sm text-slate-700 md:text-base">{s.text}</p>
              <Link href={s.href} className="btn-dark mt-6 self-start">{s.cta} →</Link>
            </div>
            {/* Product packs fanned out on the right */}
            <div className="pointer-events-none absolute -right-6 bottom-0 top-0 hidden w-1/2 sm:block">
              {s.images.slice(0, 3).map((src, k) => (
                <Image
                  key={src}
                  src={src}
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
    </div>
  );
}
