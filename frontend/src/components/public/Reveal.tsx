'use client';
// Fades and slides a block in when it comes into view.
// Content is visible in the server HTML (Google and no-JS visitors see everything); only blocks that
// start below the screen are hidden after loading, then revealed. Off for "reduce motion" users.
//
// Two modes:
// - once (default): page sections. Revealed the first time they come into view, then left alone.
//   All share ONE IntersectionObserver (shows blocks that come into view for any reason: scroll, a tab
//   switch that moves them up, a resize) and ONE scroll listener (shows blocks a fast scroll or a jump
//   such as "Explore the range" skipped over: those are above the screen and never "intersect").
// - repeat: cards in a grid (products, category tiles). Pop in EVERY time they come into view,
//   scrolling down or up: a card that is fully off screen is hidden on the side it is on, so it slides
//   in from below when scrolling down and from above when scrolling up. A shared scroll listener keeps
//   that side right for cards a jump carried past without them ever "intersecting".
//
// stagger: cards in the same row appear one after another, by their real column (works for any
// number of columns, so 2 on phones and 4 on laptops both ripple correctly).
import { useEffect, useRef, useState } from 'react';

type Props = {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  stagger?: boolean;
  as?: 'div' | 'section' | 'li';
  repeat?: boolean;
};
type State = 'static' | 'below' | 'above' | 'shown';
const STAGGER_MS = 90;

// ---------- once ----------
const waiting = new Map<Element, () => void>();
let onceObserver: IntersectionObserver | null = null;

function show(el: Element) {
  const reveal = waiting.get(el);
  if (!reveal) return;
  waiting.delete(el);
  onceObserver?.unobserve(el);
  reveal();
  if (!waiting.size) window.removeEventListener('scroll', onScrollOnce);
}

function onScrollOnce() {
  for (const el of waiting.keys()) if (el.getBoundingClientRect().top < window.innerHeight) show(el);
}

function watchOnce(el: Element, reveal: () => void) {
  onceObserver ??= new IntersectionObserver((entries) => entries.forEach((e) => e.isIntersecting && show(e.target)), {
    rootMargin: '0px 0px -10% 0px',
  });
  if (!waiting.size) window.addEventListener('scroll', onScrollOnce, { passive: true });
  waiting.set(el, reveal);
  onceObserver.observe(el);
}

function unwatchOnce(el: Element) {
  if (waiting.delete(el)) onceObserver?.unobserve(el);
  if (!waiting.size) window.removeEventListener('scroll', onScrollOnce);
}

// ---------- repeat ----------
type Entry = { set: (s: State) => void; state: State };
const repeating = new Map<Element, Entry>();
let repeatObserver: IntersectionObserver | null = null;

function setRepeat(el: Element, state: State) {
  const entry = repeating.get(el);
  if (!entry || entry.state === state) return;
  entry.state = state;
  entry.set(state);
}

// Hidden cards keep the side they are on up to date (a jump can carry them past the screen)
function onScrollRepeat() {
  for (const [el, entry] of repeating) {
    if (entry.state !== 'below' && entry.state !== 'above') continue;
    const r = el.getBoundingClientRect();
    if (r.bottom < 0) setRepeat(el, 'above');
    else if (r.top > window.innerHeight) setRepeat(el, 'below');
  }
}

function watchRepeat(el: Element, set: (s: State) => void) {
  // 15% visible: pop in. 0% visible (fully off screen): hidden, on the side it is on.
  repeatObserver ??= new IntersectionObserver(
    (entries) =>
      entries.forEach((e) => {
        if (e.intersectionRatio >= 0.15) setRepeat(e.target, 'shown');
        else if (!e.isIntersecting) setRepeat(e.target, e.boundingClientRect.top < 0 ? 'above' : 'below');
      }),
    { threshold: [0, 0.15] },
  );
  if (!repeating.size) window.addEventListener('scroll', onScrollRepeat, { passive: true });
  repeating.set(el, { set, state: 'static' });
  repeatObserver.observe(el);
}

function unwatchRepeat(el: Element) {
  repeating.delete(el);
  repeatObserver?.unobserve(el);
  if (!repeating.size) window.removeEventListener('scroll', onScrollRepeat);
}

/** Column of a card in its grid row (0 = first), from where it really is on screen. */
function columnOf(el: HTMLElement): number {
  const parent = el.parentElement;
  if (!parent || !el.offsetWidth) return 0;
  return Math.max(0, Math.round((el.getBoundingClientRect().left - parent.getBoundingClientRect().left) / el.offsetWidth));
}

export default function Reveal({ children, className = '', delay = 0, stagger = false, as: Tag = 'div', repeat = false }: Props) {
  const ref = useRef<HTMLElement>(null);
  const [state, setState] = useState<State>('static');
  const [wait, setWait] = useState(delay);

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (repeat) {
      watchRepeat(el, setState);
      return () => unwatchRepeat(el);
    }
    if (el.getBoundingClientRect().top < window.innerHeight) return; // already on screen or scrolled past
    setState('below');
    watchOnce(el, () => setState('shown'));
    return () => unwatchOnce(el);
  }, [repeat]);

  // The ripple delay comes from the card's column, worked out in advance (a delay changed after the
  // animation started would do nothing) and again on resize (2 columns on phones, 4 on laptops)
  useEffect(() => {
    if (!stagger) return;
    const update = () => ref.current && setWait(delay + columnOf(ref.current) * STAGGER_MS);
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [stagger, delay]);

  // Hidden states have no transition (the block is off screen, so the jump can't be seen). "shown" ends
  // at transform: none, so a block never keeps a transform that would trap a fixed popup inside it.
  const motion = {
    static: '',
    below: 'translate-y-8 opacity-0 transition-none',
    above: '-translate-y-8 opacity-0 transition-none',
    shown: 'transform-none opacity-100 transition-[opacity,transform] duration-700 ease-out',
  }[state];
  return (
    <Tag
      ref={ref as React.Ref<never>}
      className={`${motion} ${className}`}
      style={state === 'shown' && wait ? { transitionDelay: `${wait}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}
