'use client';
// Fades and slides a block up the first time it comes into view.
// Content is visible in the server HTML (Google and no-JS visitors see everything); only blocks that
// start below the screen are hidden after loading, then revealed. Off for "reduce motion" users.
//
// All blocks share ONE IntersectionObserver (shows blocks that come into view for any reason: scroll,
// a tab switch that moves them up, a resize) and ONE scroll listener (shows blocks a fast scroll or a
// jump such as "Explore the range" skipped over: those are above the screen and never "intersect").
import { useEffect, useRef, useState } from 'react';

type Props = { children: React.ReactNode; className?: string; delay?: number; as?: 'div' | 'section' | 'li' };

const waiting = new Map<Element, () => void>();
let observer: IntersectionObserver | null = null;

function show(el: Element) {
  const reveal = waiting.get(el);
  if (!reveal) return;
  waiting.delete(el);
  observer?.unobserve(el);
  reveal();
  if (!waiting.size) window.removeEventListener('scroll', onScroll);
}

function onScroll() {
  for (const el of waiting.keys()) if (el.getBoundingClientRect().top < window.innerHeight) show(el);
}

function watch(el: Element, reveal: () => void) {
  observer ??= new IntersectionObserver((entries) => entries.forEach((e) => e.isIntersecting && show(e.target)), {
    rootMargin: '0px 0px -10% 0px',
  });
  if (!waiting.size) window.addEventListener('scroll', onScroll, { passive: true });
  waiting.set(el, reveal);
  observer.observe(el);
}

function unwatch(el: Element) {
  if (waiting.delete(el)) observer?.unobserve(el);
  if (!waiting.size) window.removeEventListener('scroll', onScroll);
}

export default function Reveal({ children, className = '', delay = 0, as: Tag = 'div' }: Props) {
  const ref = useRef<HTMLElement>(null);
  const [state, setState] = useState<'static' | 'waiting' | 'shown'>('static');

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (el.getBoundingClientRect().top < window.innerHeight) return; // already on screen or scrolled past
    setState('waiting');
    watch(el, () => setState('shown'));
    return () => unwatch(el);
  }, []);

  // "shown" ends at transform: none (not translate-y-0), so a finished block never keeps a transform
  // that would trap a "position: fixed" popup inside it
  const motion = state === 'waiting' ? 'translate-y-8 opacity-0' : state === 'shown' ? 'transform-none opacity-100' : '';
  return (
    <Tag
      ref={ref as React.Ref<never>}
      className={`transition-[opacity,transform] duration-700 ease-out ${motion} ${className}`}
      style={state === 'shown' && delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}
